import machine
from machine import Pin, UART, I2C, PWM, WDT, Timer
from neopixel import NeoPixel

import time

import supervisor
from roboat_fsm import RoboatSM, START_PI
from power_monitor import PowerMonitor
from battery_model import BatteryModel
from soc_estimator import LFPSoCEstimator
from victron import VictronMPPT
from ina260 import INA260
from pi_link import PiLink

try:
    from version import VERSION
except ImportError:
    VERSION = 'unknown'

PI_POWER_PIN = 11
DRIVE_POWER_PIN = 7
ESC_PIN = 8
NEOPIXEL_PIN = 16

STATUS_INTERVAL_MS = 60000
START_PI_INTERVAL_MS = 10000
# A Pi powered on from off takes a while to bring up its USB host; reconnect
# once it should be ready, and again in case it was slow.
USB_RECONNECT_DELAYS_MS = (20000, 60000)
MAX_PENDING = 32

boot_ms = time.ticks_ms()
boot_number, safe_mode = supervisor.record_boot()

pi_power = Pin(PI_POWER_PIN, Pin.OUT, value=1)
np = NeoPixel(Pin(NEOPIXEL_PIN, Pin.OUT), 1)

# Both built-in UARTs are used, one for bidirectional communication with the RPi and one
# for receiving data from the Victron MPPT
rpi_uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
pi_link = PiLink(rpi_uart)


def uptime_s():
    return time.ticks_diff(time.ticks_ms(), boot_ms) // 1000


def status_fields(**extra):
    fields = {
        "version": VERSION,
        "boot": boot_number,
        "reset_cause": machine.reset_cause(),
        "uptime_s": uptime_s(),
        "pi_power": pi_power.value(),
    }
    fields.update(extra)
    return fields


def run_safe_mode():
    np[0] = (2, 0, 2)
    np.write()
    pi_link.send_update("status", status_fields(mode="safe"))
    print("SAFE MODE after {} boots without a healthy run. The watchdog is off and "
          "the Pi is powered. Fix or redeploy, delete 'bootcount', then reset.".format(boot_number))


def run():
    drive_power = Pin(DRIVE_POWER_PIN, Pin.OUT, value=0)
    esc = PWM(Pin(ESC_PIN), freq=50)
    esc.duty_ns(10)

    imu_i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000)
    mppt_uart = UART(1, baudrate=19200, tx=Pin(8), rx=Pin(9))

    def make_ina():
        return INA260(I2C(1, scl=Pin(3), sda=Pin(2), freq=400_000), 0x40)

    # Timer callbacks only queue work; the main loop runs it, so FSM
    # dispatches never interrupt each other.
    pending = []

    def post(fn):
        if len(pending) < MAX_PENDING:
            pending.append(fn)

    def schedule(delay_ms, fn):
        Timer(period=delay_ms, mode=Timer.ONE_SHOT, callback=lambda t: post(fn))

    def reconnect_usb():
        try:
            supervisor.usb_reconnect()
        except Exception as e:
            print("USB reconnect failed:", repr(e))

    def on_pi_power_on():
        for delay in USB_RECONNECT_DELAYS_MS:
            schedule(delay, reconnect_usb)

    roboat = RoboatSM(neopixel=np, pi_power_pin=pi_power, drive_power_pin=drive_power,
                      drive_pwm=esc, schedule=schedule, on_pi_power_on=on_pi_power_on)

    monitor = PowerMonitor(make_ina, VictronMPPT(mppt_uart), pi_link,
                           BatteryModel(nominal_v=12.8, nominal_ah=20), LFPSoCEstimator(),
                           roboat.dispatch, time.ticks_ms())

    def send_status(**extra):
        pi_link.send_update("status", status_fields(
            state=roboat.state, ina_errors=monitor.ina_errors,
            mppt_errors=monitor.mppt_errors, **extra))

    start_pi_timer = Timer(period=START_PI_INTERVAL_MS, mode=Timer.PERIODIC,
                           callback=lambda t: post(lambda: roboat.dispatch(START_PI)))

    liveness = supervisor.Liveness(time.ticks_ms())
    wdt = None if supervisor.wdt_disabled() else WDT(timeout=supervisor.WDT_TIMEOUT_MS)

    def feed_wdt(t):
        if wdt is not None and liveness.should_feed(time.ticks_ms()):
            wdt.feed()

    wdt_timer = Timer(period=1000, mode=Timer.PERIODIC, callback=feed_wdt)

    send_status(event="boot", wdt=wdt is not None)
    last_status_ms = time.ticks_ms()
    healthy = False

    try:
        while True:
            now = time.ticks_ms()
            liveness.alive(now)
            while pending:
                pending.pop(0)()
            if not monitor.step(now):
                time.sleep_ms(10)
            if time.ticks_diff(now, last_status_ms) >= STATUS_INTERVAL_MS:
                send_status()
                last_status_ms = now
            if not healthy and time.ticks_diff(now, boot_ms) >= supervisor.HEALTHY_AFTER_MS:
                supervisor.mark_healthy()
                healthy = True
    except KeyboardInterrupt:
        # Someone (or a deploy) is at the console. Hold the watchdog off for a
        # while; if nobody resets the board by then, it resets itself and
        # resumes normal operation.
        start_pi_timer.deinit()
        liveness.start_maintenance(time.ticks_ms())
        send_status(event="maintenance")
        print("Main loop stopped. The watchdog resets the board in {} s unless "
              "reset sooner.".format(supervisor.MAINTENANCE_S) if wdt else "Main loop stopped.")
    except Exception as e:
        supervisor.record_crash(e, time.ticks_diff(time.ticks_ms(), boot_ms))
        try:
            send_status(event="crash", error=repr(e))
            time.sleep_ms(100)
        except Exception:
            pass
        machine.reset()


if safe_mode:
    run_safe_mode()
else:
    run()
