from machine import Pin, UART, I2C, WDT
from neopixel import NeoPixel
from roboat_fsm import *

import time
import json

from victron import VictronMPPT
from ina260 import INA260
from pi_link import PiLink

# Set up the watchdog timer with a 1s timeout. It will be fed on every iteration of the
# main loop, or about every 10ms.
#wdt = WDT(timeout=1000)

bootsel_button_pin = Pin(4, Pin.IN)

np_pin = Pin(16, Pin.OUT)
np = NeoPixel(np_pin, 1)

# Solid State relay control pins
pi_power = Pin(11, Pin.OUT)
drive_power = Pin(7, Pin.OUT)

roboat = RoboatSM(neopixel =np, pi_power_pin = pi_power, drive_power_pin = drive_power)

imu_i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000)
ina260_i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400_000)

ina = INA260(ina260_i2c, 0x40)

# Both built-in UARTs are used, one for bidirectional communication with the RPi and one 
# for receiving data from the Victron MPPT
rpi_uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
mppt_uart = UART(1, baudrate=19200, tx=Pin(8), rx=Pin(9))

# The PiLink object owns the connection to the Raspberry Pi, and handles
# tracking the state of the Pi, resetting it if necessary, and ensuring
# that all sensor data reaches it eventually.
pi_link = PiLink(rpi_uart)

mppt = VictronMPPT(mppt_uart)
mppt_epoch = -1

ina260_v = 0
ina260_i = 0
ina260_p = 0
ina260_dcharge = 0
last_ticks = time.ticks_ms()

# fsm = StateMachine()

def monitor_power():
    global last_ticks
    global mppt_epoch
    global ina260_dcharge
    global ina260_v
    global ina260_i
    global ina260_p

    now = time.ticks_ms()
    dt_ms = now - last_ticks
    if dt_ms > 1000:
        ina260_i = ina.current
        ina260_v = ina.voltage
        ina260_p = ina.power
        ina260_dcharge = (
            ina260_dcharge + ina260_i * dt_ms / 1000.0
        )  # amp*S = amps * dt in seconds

        pi_link.send_update("ina260", {
            "logic_p": ina260_p,
            "logic_i": ina260_i,
            "batt_v": ina260_v,
            "logic_total_ah": ina260_dcharge / 3600.0
        })

#         print(
#             "{:.2f}V   {:.3f}A   {:.2f}W  {:.3f}Ah".format(
#                 ina260_v, ina260_i, ina260_p, ina260_dcharge / 3600
#             )
#         )
        last_ticks = now

    mppt.update()
    if mppt.active and mppt.epoch > mppt_epoch:
        pi_link.send_update("mppt", {
            "mppt_mode": mppt.tracker_mode,
            "mppt_epoch": mppt.epoch,
            "batt_v": mppt.battery_volts,
            "batt_i": mppt.battery_amps,
            "sol_v": mppt.panel_volts,
            "sol_p": mppt.panel_watts,
            "load_i": mppt.load_amps,
            "mppt_total_kwh": mppt.yield_total_kwh
        })
        mppt_epoch = mppt.epoch
        if mppt.battery_volts > 12.5:
            roboat.dispatch(MAIN_POWER_UP)
        else:
            roboat.dispatch(MAIN_POWER_DOWN)

        if mppt.battery_volts > 13.5 or mppt.panel_watts > 10:
            roboat.dispatch(ENERGY_OK)
        else:
            roboat.dispatch(ENERGY_LOW)

    else:
        time.sleep_ms(10)

    # service the watchdog timer
    # wdt.feed()



# def Init_logic():
#     # Referenced global variables
#     # ----> Here <----
#     
#     # Code that executes just once during state
#     if fsm.execute_once:
#         print("Machine in Init")
#         np[0] = (2, 0, 0)
#         np.write()
# #         print(imu_i2c.scan())
# #         print(ina260_i2c.scan())
# 
#     # Code that executes continously during state
#     pi_power.off()
#     drive_power.off()
#     monitor()

# def Run_logic():
#     global last_ticks
#     global mppt_epoch
#     global ina260_dcharge
#     global ina260_v
#     global ina260_i
#     global ina260_p
# 
#     if fsm.execute_once:
#         print("Machine in Run")
#         np[0] = (0, 0, 2)
#         np.write()
# 
#     pi_power.on()
#     drive_power.on()
#     monitor()

# Init_state = fsm.add_state(Init_logic)
# Run_state = fsm.add_state(Run_logic)

# def main_power_available():
#     return mppt.battery_volts > 12
# 
# Init_state.attach_transition(main_power_available, Run_state)

# while True:
#     fsm.run()

roboat.dispatch(WAKE)

def tick_loop(t):
    roboat.dispatch(TICK)

tick_timer = Timer()
tick_timer.init(period=1000, mode=Timer.PERIODIC, callback=tick_loop)

start_pi_timer = Timer()
start_pi_timer.init(period=10000, mode=Timer.PERIODIC, callback=lambda t: roboat.dispatch(START_PI))

while True:
    monitor_power()

