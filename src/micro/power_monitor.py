import time

from roboat_fsm import MAIN_POWER_UP, MAIN_POWER_DOWN, ENERGY_OK, ENERGY_LOW, BATTERY_LOW

INA_INTERVAL_MS = 1000
INA_REINIT_AFTER_ERRORS = 5

# The INA260 also measures battery voltage; it stands in for the MPPT when the
# MPPT hasn't delivered a frame recently.
MPPT_STALE_MS = 30000

# Main power hysteresis keeps a battery hovering near the threshold from
# power-cycling the Pi over and over.
#
# Main power also needs the MPPT's load output to be live, since that output
# feeds the DC-DC converter for the Pi (and the RP2040, which otherwise runs on
# its LiPo). The output reconnects at a higher battery voltage than the Pi may
# start at, and its own data line keeps reporting battery voltage while it's
# off. The INA260 measures the load side directly: it reads under a volt with
# the output off.
MAIN_POWER_UP_V = 12.6
MAIN_POWER_DOWN_V = 12.4
LOAD_BUS_DEAD_V = 9.0
INA_FRESH_MS = 5000
ENERGY_OK_V = 13.5
ENERGY_OK_PANEL_W = 10

# Shut the Pi down cleanly once the battery has stayed below PI_SHUTDOWN_V for
# PI_SHUTDOWN_HOLD_MS (a brief dip under load doesn't count), leaving the rest
# of the battery for the RP2040 and GPS. For LiFePO4 at the boat's light
# loads, 12.8 V is roughly 15-20% charge. The low reading only clears above
# PI_SHUTDOWN_CLEAR_V. The hard cutoff at MAIN_POWER_DOWN_V is the failsafe.
PI_SHUTDOWN_V = 12.8
PI_SHUTDOWN_CLEAR_V = 12.9
PI_SHUTDOWN_HOLD_MS = 120000
# Energy is only "OK" for starting the Pi once the battery has recovered this far.
PI_RESTART_MIN_V = 13.0

BATTERY_REPORT_MS = 10000


class PowerMonitor:
    """Samples the INA260 and Victron MPPT, reports to the Pi, and drives the FSM.

    Sensor errors are counted and survived rather than allowed to stop the
    main loop. make_ina() builds a fresh INA260 (and I2C bus) after repeated
    failures.
    """

    def __init__(self, make_ina, mppt, pi_link, battery, dispatch, now_ms):
        self.make_ina_ = make_ina
        self.ina_ = None
        self.mppt_ = mppt
        self.pi_link_ = pi_link
        self.battery_ = battery
        self.dispatch_ = dispatch

        self.last_ina_ms_ = now_ms
        self.load_bus_v_ = None
        self.load_bus_ms_ = None
        self.last_mppt_ms_ = None
        self.mppt_epoch_ = mppt.epoch
        self.mppt_frames_ = 0
        self.main_power_ = None
        self.main_power_cause = None  # "load_off", "load_bus_dead" or "low_voltage"
        self.low_since_ms_ = None
        self.last_assess_ms_ = None
        self.battery_v = None

        self.logic_charge_as_ = 0.0
        self.logic_i_ = None
        self.last_battery_report_ms_ = None
        self.ina_errors = 0
        self.ina_consecutive_errors_ = 0
        self.mppt_errors = 0

    def step(self, now_ms):
        """Do one round of work. Returns False if there was nothing to do."""
        if time.ticks_diff(now_ms, self.last_ina_ms_) >= INA_INTERVAL_MS:
            self._sample_ina(now_ms)
        return self._update_mppt(now_ms)

    def _ina(self):
        if self.ina_ is None:
            self.ina_ = self.make_ina_()
        return self.ina_

    def _sample_ina(self, now_ms):
        dt_ms = time.ticks_diff(now_ms, self.last_ina_ms_)
        self.last_ina_ms_ = now_ms
        try:
            ina = self._ina()
            current = ina.current
            voltage = ina.voltage
            power = ina.power
        except OSError:
            self.ina_errors += 1
            self.ina_consecutive_errors_ += 1
            if self.ina_consecutive_errors_ >= INA_REINIT_AFTER_ERRORS:
                self.ina_ = None
                self.ina_consecutive_errors_ = 0
            return
        self.ina_consecutive_errors_ = 0
        self.load_bus_v_ = voltage
        self.load_bus_ms_ = now_ms
        self.logic_i_ = current

        self.logic_charge_as_ += current * dt_ms / 1000.0
        self.pi_link_.send_update("ina260", {
            "logic_p": power,
            "logic_i": current,
            "batt_v": voltage,
            "logic_total_ah": self.logic_charge_as_ / 3600.0
        })

        if self._mppt_stale(now_ms):
            self._assess_battery(voltage, now_ms)

    def _mppt_stale(self, now_ms):
        return (self.last_mppt_ms_ is None
                or time.ticks_diff(now_ms, self.last_mppt_ms_) > MPPT_STALE_MS)

    def _update_mppt(self, now_ms):
        mppt = self.mppt_
        try:
            mppt.poll(now_ms)
            mppt.update()
        except (ValueError, UnicodeError):
            self.mppt_errors += 1
            return False
        if not (mppt.active and mppt.epoch > self.mppt_epoch_):
            return False
        self.mppt_epoch_ = mppt.epoch
        self.mppt_frames_ += 1

        # The first frame after boot may have been joined part way through,
        # so its fields can be missing (reading as zero).
        if self.mppt_frames_ == 1 or mppt.battery_volts <= 0:
            return True
        self.last_mppt_ms_ = now_ms

        update = {
            "mppt_mode": mppt.tracker_mode,
            "mppt_epoch": mppt.epoch,
            "batt_v": mppt.battery_volts,
            "batt_i": mppt.battery_amps,
            "sol_v": mppt.panel_volts,
            "sol_p": mppt.panel_watts,
            "load_i": mppt.load_amps,
            "mppt_total_kwh": mppt.yield_total_kwh
        }
        if mppt.load_on is not None:
            update["load_on"] = 1 if mppt.load_on else 0
        if mppt.battery_temp_c is not None:
            update["batt_temp_c"] = round(mppt.battery_temp_c, 2)
        self.pi_link_.send_update("mppt", update)
        self._update_battery_model(now_ms)

        self._assess_battery(mppt.battery_volts, now_ms)
        if ((mppt.battery_volts > ENERGY_OK_V or mppt.panel_watts > ENERGY_OK_PANEL_W)
                and mppt.battery_volts >= PI_RESTART_MIN_V):
            self.dispatch_(ENERGY_OK)
        else:
            self.dispatch_(ENERGY_LOW)
        return True

    def _update_battery_model(self, now_ms):
        mppt = self.mppt_
        logic_a = None
        if (self.load_bus_ms_ is not None
                and time.ticks_diff(now_ms, self.load_bus_ms_) <= INA_FRESH_MS
                and self.load_bus_v_ >= LOAD_BUS_DEAD_V):
            logic_a = self.logic_i_
        known = self.battery_.update(now_ms, mppt.battery_volts, mppt.battery_amps,
                                     mppt.panel_watts, logic_a,
                                     getattr(mppt, "charge_state", None),
                                     mppt.load_on)
        if known and (self.last_battery_report_ms_ is None or time.ticks_diff(
                now_ms, self.last_battery_report_ms_) >= BATTERY_REPORT_MS):
            self.last_battery_report_ms_ = now_ms
            self.pi_link_.send_update("battery", self.battery_.report())

    @property
    def battery_low_s(self):
        """How long the battery has been below PI_SHUTDOWN_V, in seconds (0 if not)."""
        if self.low_since_ms_ is None or self.last_assess_ms_ is None:
            return 0
        return time.ticks_diff(self.last_assess_ms_, self.low_since_ms_) // 1000

    def _assess_battery(self, volts, now_ms):
        if volts <= 0:
            return
        self.battery_v = volts
        self.last_assess_ms_ = now_ms
        self._assess_main_power(volts, now_ms)
        if volts < PI_SHUTDOWN_V:
            if self.low_since_ms_ is None:
                self.low_since_ms_ = now_ms
            if time.ticks_diff(now_ms, self.low_since_ms_) >= PI_SHUTDOWN_HOLD_MS:
                self.dispatch_(BATTERY_LOW)
        elif volts >= PI_SHUTDOWN_CLEAR_V:
            self.low_since_ms_ = None

    def _load_bus_fresh(self, now_ms):
        return (self.load_bus_ms_ is not None
                and time.ticks_diff(now_ms, self.load_bus_ms_) <= INA_FRESH_MS)

    def _load_output_dead(self, now_ms):
        """Why the load output counts as dead ("load_off" or "load_bus_dead"), or None."""
        if not self._mppt_stale(now_ms) and self.mppt_.load_on is False:
            return "load_off"
        if self._load_bus_fresh(now_ms) and self.load_bus_v_ < LOAD_BUS_DEAD_V:
            return "load_bus_dead"
        return None

    def load_output_live(self, now_ms):
        """False once the MPPT says its load output is off, or the INA260 reads it dead."""
        return self._load_output_dead(now_ms) is None

    def main_power_report(self, now_ms):
        """Fields for the event that cuts the Pi: which check took main power down,
        and the INA260's load bus reading if it's fresh (battery_v is in every status)."""
        fields = {"power_cause": self.main_power_cause}
        if self._load_bus_fresh(now_ms):
            fields["load_bus_v"] = round(self.load_bus_v_, 3)
        return fields

    def _assess_main_power(self, volts, now_ms):
        dead = self._load_output_dead(now_ms)
        if dead is not None:
            self._set_main_power(False, dead)
        elif self.main_power_ is not True and volts > MAIN_POWER_UP_V:
            self._set_main_power(True)
        elif self.main_power_ is not False and volts < MAIN_POWER_DOWN_V:
            self._set_main_power(False, "low_voltage")
        elif self.main_power_ is None:
            # Inside the hysteresis band with no history: pick the nearer side.
            self._set_main_power(volts >= (MAIN_POWER_UP_V + MAIN_POWER_DOWN_V) / 2,
                                 "low_voltage")
        self.dispatch_(MAIN_POWER_UP if self.main_power_ else MAIN_POWER_DOWN)

    def _set_main_power(self, on, cause=None):
        # Keep the cause from the moment main power went down: that's the
        # dispatch that cuts the Pi, and a later check failing too changes nothing.
        if not on and self.main_power_ is not False:
            self.main_power_cause = cause
        self.main_power_ = on
