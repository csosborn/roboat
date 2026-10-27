import machine
from machine import Pin, UART, I2C, PWM, WDT, Timer, ADC
from neopixel import NeoPixel

import os
import time

import supervisor
import power_policy
from roboat_fsm import RoboatSM, START_PI, PI_HEARTBEAT, PI_HEARTBEAT_TO, PI_STOPPED
from power_monitor import PowerMonitor
from battery_model import BatteryModel
from soc_estimator import LFPSoCEstimator
from victron import VictronMPPT
from ina260 import INA260
from pi_link import PiLink, PiPresence
from clock import Clock
from gps import GpsMonitor
from shared_bus import SharedBus
from scheduler import Scheduler
from telemetry_log import TelemetryLog
from pi_shutdown import PiShutdown
from power_sense import LipoSense, PiSupplyCheck, LIPO_PIN, PI_SUPPLY_GOOD_PIN

try:
    from version import VERSION
except ImportError:
    VERSION = 'unknown'

PI_POWER_PIN = 11
DRIVE_POWER_PIN = 7
ESC_PIN = 8
NEOPIXEL_PIN = 16
# The Victron only transmits, so UART1's TX goes to an otherwise unused pin
# (GPIO8 is the ESC's).
MPPT_TX_PIN = 24
MPPT_RX_PIN = 9
# An Adafruit BNO085 on the STEMMA QT chain (I2C1). Not read yet.
IMU_ADDR = 0x4A

STATUS_INTERVAL_MS = 60000
# While the Pi isn't listening, store a snapshot of the latest readings this often.
SNAPSHOT_INTERVAL_MS = 60000
START_PI_INTERVAL_MS = 10000
SAFE_MODE_RETRY_MS = 3600000
# Room for a whole deploy chunk (about 1 KB) arriving while the REPL is busy;
# the link has no flow control.
PI_UART_RXBUF = 4096
# Moving the REPL onto the Pi link lets deploys run without USB.
SERIAL_REPL = hasattr(os, 'dupterm')

# Timers that must outlive the function creating them. An unreferenced
# machine.Timer can be garbage-collected, which cancels it.
keep_alive = []

boot_ms = time.ticks_ms()
boot_number, safe_mode = supervisor.record_boot()

# boot.py has already chosen the Pi's power; keep it, but make sure the pin
# is an output even if boot.py didn't run.
pi_power = Pin(PI_POWER_PIN)
pi_power = Pin(PI_POWER_PIN, Pin.OUT, value=pi_power.value())
np = NeoPixel(Pin(NEOPIXEL_PIN, Pin.OUT), 1)

# Both built-in UARTs are used, one for bidirectional communication with the RPi and one
# for receiving data from the Victron MPPT
rpi_uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1), rxbuf=PI_UART_RXBUF, txbuf=1024)
clock = Clock()
pi_link = PiLink(rpi_uart, clock)


class MaintenanceRequested(Exception):
    pass


def attach_repl_to_pi_link():
    if SERIAL_REPL:
        os.dupterm(rpi_uart)


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
    print("SAFE MODE after {} boots without a healthy run. The watchdog is off and the Pi's "
          "power is left as boot.py set it. Normal operation is retried in {} minutes."
          .format(boot_number, SAFE_MODE_RETRY_MS // 60000))
    attach_repl_to_pi_link()

    def retry(t):
        supervisor.mark_healthy()
        machine.reset()

    keep_alive.append(Timer(period=SAFE_MODE_RETRY_MS, mode=Timer.ONE_SHOT, callback=retry))


def run():
    drive_power = Pin(DRIVE_POWER_PIN, Pin.OUT, value=0)
    esc = PWM(Pin(ESC_PIN), freq=50)
    esc.duty_ns(10)

    mppt_uart = UART(1, baudrate=19200, tx=Pin(MPPT_TX_PIN), rx=Pin(MPPT_RX_PIN))

    # The INA260, the GPS and the IMU (on the STEMMA QT chain) share I2C1.
    i2c1 = SharedBus(lambda: I2C(1, scl=Pin(3), sda=Pin(2), freq=400_000))
    try:
        imu_present = 1 if IMU_ADDR in i2c1.get().scan() else 0
    except OSError:
        imu_present = None
    lipo = LipoSense(ADC(LIPO_PIN))
    pi_supply = PiSupplyCheck(Pin(PI_SUPPLY_GOOD_PIN, Pin.IN), pi_power, time.ticks_ms())

    def lipo_v():
        try:
            return lipo.volts()
        except OSError:
            return None
    ina_made = []

    def make_ina():
        # Called again only after repeated INA260 errors; rebuild the bus too.
        if ina_made:
            i2c1.rebuild()
        ina_made.append(True)
        return INA260(i2c1.get(), 0x40)

    tasks = Scheduler()

    def schedule(delay_ms, fn):
        tasks.after(delay_ms, fn)

    shutdown = PiShutdown()

    def request_pi_shutdown():
        shutdown.start(time.ticks_ms(), "low_battery")

    def report_event(event, **fields):
        report(event=event, **fields)

    roboat = RoboatSM(neopixel=np, pi_power_pin=pi_power, drive_power_pin=drive_power,
                      drive_pwm=esc, schedule=schedule,
                      record_pi_power=power_policy.ChoiceRecorder(),
                      request_pi_shutdown=request_pi_shutdown, notify=report_event)

    monitor = PowerMonitor(make_ina, VictronMPPT(mppt_uart), pi_link,
                           BatteryModel(nominal_v=12.8, nominal_ah=20), LFPSoCEstimator(),
                           roboat.dispatch, time.ticks_ms())
    gps = GpsMonitor(i2c1, pi_link, clock, time.ticks_ms())

    presence = PiPresence()
    try:
        tlog = TelemetryLog(time.ticks_ms())
    except OSError:
        tlog = None
    unstorable = [0]  # snapshots skipped because GPS time wasn't known yet

    def fs_free_kb():
        try:
            st = os.statvfs('/')
            return st[0] * st[4] // 1024
        except OSError:
            return -1

    def current_status(**extra):
        fields = status_fields(
            state=roboat.state, ina_errors=monitor.ina_errors,
            mppt_errors=monitor.mppt_errors, gps_mode=gps.mode, gps_errors=gps.errors,
            gps_fixes=gps.fixes, time_valid=clock.valid, i2c_rebuilds=i2c1.rebuilds,
            pi_up=1 if presence.listening else 0, fs_free_kb=fs_free_kb(),
            log_unstorable=unstorable[0], battery_v=monitor.battery_v,
            battery_low_s=monitor.battery_low_s,
            restart_blocked=1 if roboat.restart_blocked_ else 0, lipo_v=lipo_v(),
            pi_supply_good=1 if pi_supply.good else 0, imu_present=imu_present, **extra)
        if tlog is not None:
            fields.update(log_backlog=tlog.backlog, log_bytes=tlog.stored_bytes,
                          log_dropped=tlog.dropped, log_replayed=tlog.replayed)
        else:
            fields.update(log_error=1)
        return {k: v for k, v in fields.items() if v is not None}

    def send_status(**extra):
        pi_link.send_update("status", current_status(**extra))

    def report(**extra):
        """A status record that must not be lost (an event): sent, and stored too.

        The Pi may already be gone without the heartbeat timeout having noticed
        yet (a power cut takes it down at once), so whether it's listening
        can't be trusted here. Replaying a record the Pi already has is harmless.
        """
        msg = pi_link.send_update("status", current_status(**extra))
        if tlog is not None:
            store(msg, time.ticks_ms())

    def store(msg, now):
        if "utc_ms" in msg:
            tlog.record(msg, now)
        else:
            unstorable[0] += 1

    snapshotted = {}  # src -> the message last stored for it, so a stale one isn't stored twice

    def store_snapshot(now, **status_extra):
        if tlog is None:
            return
        for src in sorted(pi_link.latest):
            msg = pi_link.latest[src]
            if src != "status" and snapshotted.get(src) is not msg:
                store(msg, now)
                snapshotted[src] = msg
        store(pi_link.message("status", current_status(**status_extra)), now)

    def flush_log():
        if tlog is not None:
            try:
                tlog.flush(time.ticks_ms())
            except OSError:
                pass

    tasks.every(START_PI_INTERVAL_MS, lambda: roboat.dispatch(START_PI))

    liveness = supervisor.Liveness(time.ticks_ms())
    wdt = None if supervisor.wdt_disabled() else WDT(timeout=supervisor.WDT_TIMEOUT_MS)

    def feed_wdt(t):
        if wdt is not None and liveness.should_feed(time.ticks_ms()):
            wdt.feed()

    # This one stays a hardware timer: it must keep running after the main
    # loop stops for maintenance.
    keep_alive.append(Timer(period=1000, mode=Timer.PERIODIC, callback=feed_wdt))

    report(event="boot", wdt=wdt is not None, serial_repl=SERIAL_REPL)
    last_status_ms = time.ticks_ms()
    last_snapshot_ms = time.ticks_ms()
    healthy = False

    try:
        while True:
            now = time.ticks_ms()
            liveness.alive(now)
            tasks.run_due(now)
            for command in pi_link.poll_commands():
                if command["cmd"] == "maintenance" and SERIAL_REPL:
                    raise MaintenanceRequested()
                if command["cmd"] == "hb":
                    came_back = presence.heard(now)
                    roboat.dispatch(PI_HEARTBEAT)
                    ack = command.get("ack")
                    if tlog is not None and isinstance(ack, int):
                        tlog.ack(ack)
                    if came_back:
                        report(event="pi_up")
            if presence.check(now):
                roboat.dispatch(PI_HEARTBEAT_TO)
                store_snapshot(now, event="pi_down")
                last_snapshot_ms = now
            if not presence.listening and time.ticks_diff(now, last_snapshot_ms) >= SNAPSHOT_INTERVAL_MS:
                store_snapshot(now)
                last_snapshot_ms = now
            if shutdown.step(now, presence.listening,
                             lambda reason: pi_link.send_request("shutdown", reason=reason)):
                if shutdown.timed_out:
                    report(event="pi_shutdown_timeout")
                roboat.dispatch(PI_STOPPED)
            pi_supply.step(now, report_event)
            if tlog is not None:
                tlog.step(now, presence.listening, pi_link.send_line)
            gps.step(now)
            if not monitor.step(now):
                time.sleep_ms(10)
            if time.ticks_diff(now, last_status_ms) >= STATUS_INTERVAL_MS:
                send_status()
                last_status_ms = now
            if not healthy and time.ticks_diff(now, boot_ms) >= supervisor.HEALTHY_AFTER_MS:
                supervisor.mark_healthy()
                healthy = True
    except (KeyboardInterrupt, MaintenanceRequested) as e:
        # Someone (or a deploy) is at the console. Hold the watchdog off for a
        # while; if nobody resets the board by then, it resets itself and
        # resumes normal operation.
        liveness.start_maintenance(time.ticks_ms())
        via_pi_link = isinstance(e, MaintenanceRequested)
        report(event="maintenance", via="pi_link" if via_pi_link else "console")
        flush_log()
        if via_pi_link:
            attach_repl_to_pi_link()
        print("Main loop stopped. The watchdog resets the board in {} s unless "
              "reset sooner.".format(supervisor.MAINTENANCE_S) if wdt else "Main loop stopped.")
    except Exception as e:
        supervisor.record_crash(e, time.ticks_diff(time.ticks_ms(), boot_ms))
        try:
            report(event="crash", error=repr(e))
        except Exception:
            pass
        flush_log()
        time.sleep_ms(100)
        machine.reset()


if safe_mode:
    run_safe_mode()
else:
    run()
