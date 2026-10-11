# Compute

- Initial tests used a Raspberry Pi Zero 2 W board as the main compute, but the 512MB of memory proved for containerized InfluxDB and Telegraf, never mind Grafana or actual application logic. 
- Testbed development now proceeding with a Raspberry Pi 3+ (1GB memory), which is performing better. 
- 8GB Raspberry Pi 4 on order.


## Components

- Raspberry Pi 4 Model B with 8GB memory
    - RP2040 (below)
        - UART connection for operational data
        - USB connection for programming only. Its 5V (VBUS) line must be cut: the RP2040 runs from its own supply, and a live VBUS back-powers the Pi through its USB port, so the relay can no longer switch the Pi off.

- RP2040 Feather microcontroller running MicroPython
    - UART-connected Victron MPPT
    - I2C-connected INA260 current/voltage monitor reading main battery voltage and aggregate load of compute and sensors
    - I2C-connected 9-DOF IMU (I2C0, GPIO 12/13)
    - I2C-connected GPS: Adafruit Mini GPS PA1010D on the STEMMA QT connector (I2C1, GPIO 2/3, shared with the INA260). The RP2040 keeps position and UTC while the Pi is off, and timestamps its messages (`utc_ms`) once it has a fix.
    - propulsion motor ESC
    - rudder servo


## System States

There are two compute elements of interest when it comes to understanding the overall system state: the RP2040 microcontroller and the RPi 4 main compute. The former manages basic power system data collection and control, and will be powered on as long as any energy is available in either the main battery or the low-voltage backup battery. The RPi provides long-term data retention, tracking, planning, and communications, and may or may not be powered on at any given time, depending on main battery power availability. It may be shut down preemptively to conserve power, and is not served by the low-voltage backup.

### Power safety rules

The RP2040 must be able to restart, crash, or be reprogrammed without taking the Pi down with it, and must never leave the Pi half-powered.

- The Pi's power relay (GPIO11, high = on) must stay on while the RP2040 is in reset, so that an RP2040 restart doesn't cut a running Pi. **It doesn't yet.** A 10k pull-up to 3.3V turned out too weak to drive the relay's input on its own (measured 2026-10-11: with the pin in its reset state, the Pi's supply current fell by the whole of its draw). Until the relay gets a driver that holds it on through a reset (for example a logic-level MOSFET with a gate pull-up), any RP2040 reset briefly cuts the Pi, and firmware updates use `tools/deploy.sh --flash-halt`.
- `boot.py` settles the relay before anything else runs (`power_policy.py`):
  - Power-on reset (a cold start, including the reset button): Pi off. The whole system may be waking at dawn on a nearly empty battery, and the Pi must not start, brown out, and repeat. It starts only when the FSM's energy rules allow.
  - Watchdog reset (a crash, a hang, or the reset at the end of a deploy): restore the relay state the firmware last chose deliberately, which it records in a `pi_power` file on each change.
  - Soft reset (Ctrl-D): leave the relay alone.
- The firmware only changes Pi power deliberately: starting it when energy allows, and cutting it on loss of main power or after a requested shutdown.
- Once the relay holds through a reset, it will also be on for the moment between the RP2040 powering up and `boot.py` running. At a dawn wake-up that only happens once the MPPT's load output has reconnected.
- No other connection may supply power to the Pi while the relay is off (see the USB note above). With the relay off, the Pi's red LED must go fully dark.
- The watchdog is fed only while the main loop is running, so a crash or hang ends in a reset. Interrupting the main loop from the console (Ctrl-C, as a deploy does) holds the watchdog off for 15 minutes. A `nowdt` file on the RP2040 disables it for bench work.
- After three consecutive boots that crash before running healthily for a minute, the RP2040 comes up in safe mode: watchdog off, relay left as `boot.py` set it, REPL free for a deploy to repair it. Safe mode retries normal operation after an hour. Crashes are logged to `crash.log` on the RP2040.

### States

- Init: initial state, where no information about the system is yet available. The Pi's power is left alone until the first battery voltage reading.
- NoMainPower: superstate encompassing all operations where the main battery is exhausted or too low a voltage. Entering it cuts power to the Pi and the drive.
  - Monitor: stable state wherein the RP2040 is monitoring and recording power levels but the ship is otherwise idle, waiting for sufficient power to be available for normal operations.
- MainPower: the main battery is above the main-power threshold (12.6V up, 12.4V down).
  - AwaitPower: not enough energy to start the Pi. If the Pi is already running (for example after an RP2040 reset), it is left running and the state moves to NoPiComms.
  - PiOff, NoPiComms, PiAlive, PiStopping: the Pi's lifecycle.

The battery voltage comes from the Victron MPPT, or from the INA260 when the MPPT hasn't reported for 30 seconds.

```mermaid
stateDiagram
    [*] --> Init
    state NoMainPower {
        direction LR
        [*] --> Monitor
    }
    state MainPower {
        [*] --> AwaitPower
        AwaitPower --> PiOff : energy_ok
        AwaitPower --> NoPiComms : pi_already_on
        PiOff --> AwaitPower : energy_low
        PiOff --> NoPiComms : start_pi
        NoPiComms --> PiAlive : pi_hb
        PiAlive --> NoPiComms : pi_hb_to
        PiAlive --> PiStopping : stop_pi
        PiStopping --> PiOff : pi_stopped (30s)
    }
    Init --> MainPower : main_power_up
    Init --> NoMainPower : main_power_down
    NoMainPower --> MainPower : main_power_up
    MainPower --> NoMainPower : main_power_down

```