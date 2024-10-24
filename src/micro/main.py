from machine import Pin, UART
from neopixel import NeoPixel

import time
import json

from victron import VictronMPPT

bootsel_button_pin = Pin(4, Pin.IN)

np_pin = Pin(16, Pin.OUT)
np = NeoPixel(np_pin, 1)

np[0] = (0, 2, 0)
np.write()

rpi_uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
mppt_uart = UART(1, baudrate=19200, tx=Pin(8), rx=Pin(9))

mppt = VictronMPPT()
mppt_epoch = -1
while True:
    mppt_line = mppt_uart.readline()
    if mppt_line:
        try:
            mppt.update(mppt_line.decode('ascii', 'ignore'))
        except UnicodeError as e:
            pass
        if mppt.active and mppt.epoch > mppt_epoch:
            # print("{} Mode: {}  Batt: {}V {}A  Panel: {}V {}W  Load: {}A   Yield: {}kWh".format(mppt.epoch, mppt.tracker_mode, mppt.battery_volts, mppt.battery_amps, mppt.panel_volts, mppt.panel_watts, mppt.load_amps, mppt.yield_total_kwh))
            update_msg = {
                "offset_s": 0,
                "mppt_mode": mppt.tracker_mode,
                "mppt_epoch": mppt.epoch,
                "batt_v": mppt.battery_volts,
                "batt_i": mppt.battery_amps,
                "sol_v": mppt.panel_volts,
                "sol_p": mppt.panel_watts,
                "load_i": mppt.load_amps,
                "mppt_total_kwh": mppt.yield_total_kwh
            }
            update_json = json.dumps(update_msg)
            rpi_uart.write(update_json)
            rpi_uart.write("\r\n")
            mppt_epoch = mppt.epoch
    else:
        time.sleep_ms(10)


