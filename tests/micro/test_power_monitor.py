import power_monitor as pm
from roboat_fsm import MAIN_POWER_UP, MAIN_POWER_DOWN, ENERGY_OK, ENERGY_LOW, BATTERY_LOW


class FakeINA:
    def __init__(self, volts=13.2, fail=False):
        self.volts = volts
        self.fail = fail

    def _read(self, value):
        if self.fail:
            raise OSError(5)
        return value

    @property
    def current(self):
        return self._read(0.4)

    @property
    def voltage(self):
        return self._read(self.volts)

    @property
    def power(self):
        return self._read(5.0)


class FakeMPPT:
    def __init__(self):
        self.active = False
        self.epoch = 0
        self.battery_volts = 0
        self.battery_amps = 0
        self.panel_volts = 0
        self.panel_watts = 0
        self.load_amps = 0
        self.tracker_mode = 0
        self.load_on = True
        self.yield_total_kwh = 0
        self.battery_temp_c = None
        self.polls = []
        self.raise_on_update = None

    def poll(self, now_ms):
        self.polls.append(now_ms)

    def update(self):
        if self.raise_on_update:
            raise self.raise_on_update

    def frame(self, volts, panel_w=0):
        self.active = True
        self.epoch += 1
        self.battery_volts = volts
        self.panel_watts = panel_w


class FakeLink:
    def __init__(self):
        self.sent = []

    def send_update(self, src, data):
        self.sent.append((src, data))


class FakeBattery:
    def __init__(self):
        self.updates = []

    def update(self, now, v, i, panel_w, logic_a, charger_state):
        self.updates.append((now, v, i, panel_w, logic_a, charger_state))
        return True

    def report(self):
        return {"soc": 0.5}


def make(ina=None):
    inas = []
    events = []

    def make_ina():
        inas.append(ina or FakeINA())
        return inas[-1]

    mppt = FakeMPPT()
    mon = pm.PowerMonitor(make_ina, mppt, FakeLink(), FakeBattery(),
                          events.append, now_ms=0)
    return mon, mppt, events, inas


def test_first_mppt_frame_is_ignored():
    mon, mppt, events, _ = make()
    mppt.frame(volts=0)
    mon.step(10)
    assert events == []
    mppt.frame(volts=13.2)
    mon.step(20)
    assert events == [MAIN_POWER_UP, ENERGY_LOW]


def test_frame_without_battery_voltage_is_ignored():
    mon, mppt, events, _ = make()
    mppt.frame(volts=13.2)
    mon.step(10)
    mppt.frame(volts=0)
    mon.step(20)
    assert events == []


def test_ina_voltage_used_until_mppt_reports():
    mon, mppt, events, _ = make(FakeINA(volts=12.0))
    mon.step(1000)
    assert events == [MAIN_POWER_DOWN]


def test_mppt_preferred_while_fresh_and_ina_takes_over_when_stale():
    mon, mppt, events, _ = make(FakeINA(volts=12.0))
    mppt.frame(13.6)
    mon.step(1)
    mppt.frame(13.6)
    mon.step(2)
    events.clear()
    mon.step(1000)
    assert events == []
    mon.step(1000 + pm.MPPT_STALE_MS + 1000)
    assert events == [MAIN_POWER_DOWN]


def test_hysteresis_prevents_flapping():
    mon, mppt, events, _ = make()
    mppt.frame(13.0)
    mon.step(1)
    for i, v in enumerate([13.0, 12.5, 12.45, 12.55, 12.39, 12.5, 12.59, 12.61]):
        mppt.frame(v)
        mon.step(2 + i)
    power_events = [e for e in events if e in (MAIN_POWER_UP, MAIN_POWER_DOWN)]
    assert power_events == [MAIN_POWER_UP] * 4 + [MAIN_POWER_DOWN] * 3 + [MAIN_POWER_UP]


def test_energy_ok_from_voltage_or_sun():
    mon, mppt, events, _ = make()
    mppt.frame(13.0)
    mon.step(1)
    mppt.frame(13.0, panel_w=50)
    mon.step(2)
    mppt.frame(13.7, panel_w=0)
    mon.step(3)
    assert [e for e in events if e in (ENERGY_OK, ENERGY_LOW)] == [ENERGY_OK, ENERGY_OK]


def test_ina_errors_are_survived_and_bus_rebuilt():
    mon, mppt, events, inas = make(FakeINA(fail=True))
    for k in range(1, pm.INA_REINIT_AFTER_ERRORS + 2):
        mon.step(k * 1000)
    assert mon.ina_errors == pm.INA_REINIT_AFTER_ERRORS + 1
    assert len(inas) == 2


def test_mppt_parse_errors_are_counted():
    mon, mppt, events, _ = make()
    mppt.raise_on_update = ValueError("bad field")
    assert mon.step(1) is False
    assert mon.mppt_errors == 1


def frames(mon, mppt, volts, start_ms, count, step_ms=1000, panel_w=0):
    t = start_ms
    for _ in range(count):
        mppt.frame(volts, panel_w)
        mon.step(t)
        t += step_ms
    return t


def test_battery_low_needs_a_sustained_low_voltage():
    mon, mppt, events, _ = make()
    t = frames(mon, mppt, 13.0, 0, 2)
    t = frames(mon, mppt, 12.7, t, 60)  # one minute low: not yet
    assert BATTERY_LOW not in events
    t = frames(mon, mppt, 12.85, t, 30)  # inside the band: still counting
    t = frames(mon, mppt, 12.7, t, 40)
    assert BATTERY_LOW in events


def test_recovery_above_the_clear_level_resets_the_timer():
    mon, mppt, events, _ = make()
    t = frames(mon, mppt, 13.0, 0, 2)
    t = frames(mon, mppt, 12.7, t, 100)
    t = frames(mon, mppt, 12.95, t, 1)
    t = frames(mon, mppt, 12.7, t, 100)
    assert BATTERY_LOW not in events


def test_sun_alone_does_not_restart_the_pi_on_a_flat_battery():
    mon, mppt, events, _ = make()
    t = frames(mon, mppt, 12.9, 0, 3, panel_w=40)
    assert ENERGY_OK not in events
    frames(mon, mppt, 13.3, t, 1, panel_w=40)
    assert events[-1] == ENERGY_OK


def power_events(events):
    return [e for e in events if e in (MAIN_POWER_UP, MAIN_POWER_DOWN)]


def test_no_main_power_while_the_load_output_is_off():
    # The Victron reconnects its load output above 13.2 V, but reports the
    # battery voltage all along; the Pi must not be started on a dead supply.
    mon, mppt, events, _ = make()
    mppt.load_on = False
    mppt.frame(13.1)
    mon.step(1)
    mppt.frame(13.1, panel_w=50)
    mon.step(2)
    assert power_events(events) == [MAIN_POWER_DOWN]
    mppt.load_on = True
    mppt.frame(13.2, panel_w=50)
    mon.step(3)
    assert power_events(events) == [MAIN_POWER_DOWN, MAIN_POWER_UP]
    assert events[-1] == ENERGY_OK


def test_dead_load_bus_on_the_ina_means_no_main_power():
    mon, mppt, events, _ = make(FakeINA(volts=0.6))
    mppt.frame(13.3)
    mon.step(1)
    mon.step(1000)  # INA sample
    mppt.frame(13.3, panel_w=50)
    mon.step(1001)
    assert MAIN_POWER_UP not in events and power_events(events)[-1] == MAIN_POWER_DOWN


def test_cause_when_the_mppt_reports_the_load_output_off():
    mon, mppt, events, _ = make()
    mppt.frame(13.3)
    mon.step(1)
    mppt.frame(13.3)
    mon.step(2)
    mppt.load_on = False
    mppt.frame(13.3)
    mon.step(3)
    assert power_events(events)[-1] == MAIN_POWER_DOWN
    assert mon.main_power_report(3) == {"power_cause": "load_off"}


def test_cause_and_reading_when_the_load_bus_dies():
    ina = FakeINA(volts=13.3)
    mon, mppt, events, _ = make(ina)
    mppt.frame(13.3)
    mon.step(1)
    mon.step(1000)
    mppt.frame(13.3)
    mon.step(1001)
    assert power_events(events)[-1] == MAIN_POWER_UP
    ina.volts = 3.21
    mon.step(2000)  # INA sample
    mppt.frame(13.3)
    mon.step(2001)
    assert power_events(events)[-1] == MAIN_POWER_DOWN
    assert mon.main_power_report(2001) == {"power_cause": "load_bus_dead", "load_bus_v": 3.21}
    # An old reading is left out rather than reported as current.
    assert "load_bus_v" not in mon.main_power_report(2000 + pm.INA_FRESH_MS + 1)


def test_cause_when_the_battery_voltage_drops():
    mon, mppt, events, _ = make()
    mppt.frame(13.0)
    mon.step(1)
    mppt.frame(13.0)
    mon.step(2)
    mppt.frame(12.3)
    mon.step(3)
    assert power_events(events)[-1] == MAIN_POWER_DOWN
    assert mon.main_power_report(3)["power_cause"] == "low_voltage"


def test_cause_is_the_first_check_that_failed():
    mon, mppt, events, _ = make()
    mppt.frame(13.0)
    mon.step(1)
    mppt.frame(13.0)
    mon.step(2)
    mppt.frame(12.3)
    mon.step(3)
    mppt.load_on = False  # the Victron switches the output off afterwards
    mppt.frame(12.0)
    mon.step(4)
    assert mon.main_power_report(4)["power_cause"] == "low_voltage"


def test_unknown_load_state_does_not_block_main_power():
    mon, mppt, events, _ = make()
    mppt.load_on = None
    mppt.frame(13.3)
    mon.step(1)
    mppt.frame(13.3)
    mon.step(2)
    assert power_events(events) == [MAIN_POWER_UP]
    assert "load_on" not in mon.pi_link_.sent[-1][1]


def test_battery_temperature_is_sent_only_when_known():
    mon, mppt, events, _ = make()
    mppt.frame(13.3)
    mon.step(1)
    mppt.frame(13.3)
    mon.step(2)
    assert "batt_temp_c" not in mon.pi_link_.sent[-1][1]
    mppt.battery_temp_c = 16.254
    mppt.frame(13.3)
    mon.step(3)
    assert mon.pi_link_.sent[-1][1]["batt_temp_c"] == 16.25
    assert mppt.polls == [1, 2, 3]


def test_battery_model_gets_the_ina_current_only_while_fresh_and_live():
    mon, mppt, events, _ = make()
    battery = mon.battery_
    mppt.frame(13.2)
    mon.step(1)
    mon.step(1000)            # INA sample: 0.4 A
    mppt.frame(13.2)
    mon.step(1001)
    assert battery.updates[-1][4] == 0.4
    mon.last_ina_ms_ = 10 ** 9  # no more INA samples
    mppt.frame(13.2)
    mon.step(1001 + pm.INA_FRESH_MS + 1)
    assert battery.updates[-1][4] is None


def test_battery_reports_are_rate_limited():
    mon, mppt, events, _ = make()
    mppt.frame(13.2)
    mon.step(1)
    for t in range(2, 20000, 1000):
        mppt.frame(13.2)
        mon.step(t)
    sent = [d for src, d in mon.pi_link_.sent if src == "battery"]
    assert len(sent) == 2


def test_battery_message_keeps_its_source():
    import soc_model
    from pi_link import PiLink

    class Uart:
        def write(self, s):
            pass

    link = PiLink(Uart(), None)
    m = soc_model.SocModel(store=None)
    m.update(0, 13.24, -0.28, 0)
    assert link.send_update("battery", m.report())["src"] == "battery"
