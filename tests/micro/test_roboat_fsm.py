import pytest

from fakes import FakePin, FakePWM, FakeNeoPixel
import roboat_fsm as fsm


class Harness:
    def __init__(self, pi_on):
        self.pi = FakePin(1 if pi_on else 0)
        self.drive = FakePin(1)
        self.scheduled = []
        self.power_on_calls = 0
        self.recorded = []
        self.events = []
        self.shutdown_requests = 0
        self.sm = fsm.RoboatSM(FakeNeoPixel(), self.pi, self.drive, FakePWM(),
                               schedule=lambda ms, fn: self.scheduled.append((ms, fn)),
                               on_pi_power_on=self._powered_on,
                               record_pi_power=self.recorded.append,
                               request_pi_shutdown=self._request_shutdown,
                               notify=lambda event, **f: self.events.append(event))

    def _request_shutdown(self):
        self.shutdown_requests += 1

    def _powered_on(self):
        self.power_on_calls += 1

    def run_scheduled(self):
        jobs, self.scheduled = self.scheduled, []
        for _, fn in jobs:
            fn()


@pytest.mark.parametrize("pi_on", [True, False])
def test_startup_leaves_pi_power_alone(pi_on):
    h = Harness(pi_on)
    assert h.sm.state == 'Init'
    assert h.pi.value() == (1 if pi_on else 0)
    assert h.drive.value() == 0


def test_running_pi_survives_rp2040_reset():
    h = Harness(pi_on=True)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    assert h.sm.state == 'NoPiComms'
    h.sm.dispatch(fsm.ENERGY_LOW)
    h.sm.dispatch(fsm.START_PI)
    assert h.sm.state == 'NoPiComms'
    assert h.pi.value() == 1
    assert h.power_on_calls == 0


def test_pi_started_only_when_energy_ok():
    h = Harness(pi_on=False)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    assert h.sm.state == 'AwaitPower'
    h.sm.dispatch(fsm.START_PI)
    assert h.pi.value() == 0
    h.sm.dispatch(fsm.ENERGY_OK)
    assert h.sm.state == 'PiOff'
    h.sm.dispatch(fsm.START_PI)
    assert h.sm.state == 'NoPiComms'
    assert h.pi.value() == 1
    assert h.power_on_calls == 1


@pytest.mark.parametrize("pi_on", [True, False])
def test_no_main_power_at_boot_cuts_pi(pi_on):
    h = Harness(pi_on)
    h.sm.dispatch(fsm.MAIN_POWER_DOWN)
    assert h.sm.state == 'Monitor'
    assert h.pi.value() == 0


def test_losing_main_power_cuts_pi_and_recovery_waits_for_energy():
    h = Harness(pi_on=True)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.MAIN_POWER_DOWN)
    assert h.sm.state == 'Monitor'
    assert h.pi.value() == 0
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    assert h.sm.state == 'AwaitPower'
    assert h.pi.value() == 0


def running_pi():
    h = Harness(pi_on=True)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.PI_HEARTBEAT)
    assert h.sm.state == 'PiAlive'
    return h


def test_low_battery_shuts_the_pi_down_cleanly():
    h = running_pi()
    h.sm.dispatch(fsm.BATTERY_LOW)
    assert h.sm.state == 'PiStopping' and h.shutdown_requests == 1
    assert h.pi.value() == 1  # nothing is cut until the Pi has halted
    h.sm.dispatch(fsm.PI_STOPPED)
    assert h.sm.state == 'AwaitPower' and h.pi.value() == 0
    assert h.events == ["pi_shutdown_requested", "pi_power_cut"]


def test_low_battery_also_stops_a_pi_that_is_not_talking():
    h = Harness(pi_on=True)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    assert h.sm.state == 'NoPiComms'
    h.sm.dispatch(fsm.BATTERY_LOW)
    assert h.sm.state == 'PiStopping'


def test_low_battery_ignored_while_the_pi_is_off():
    h = Harness(pi_on=False)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.BATTERY_LOW)
    assert h.sm.state == 'AwaitPower' and h.shutdown_requests == 0


def test_no_restart_until_the_holdoff_expires():
    h = running_pi()
    h.sm.dispatch(fsm.BATTERY_LOW)
    h.sm.dispatch(fsm.PI_STOPPED)
    h.sm.dispatch(fsm.ENERGY_OK)
    assert h.sm.state == 'AwaitPower'
    assert [ms for ms, _ in h.scheduled] == [fsm.PI_RESTART_HOLDOFF_MS]
    h.run_scheduled()
    h.sm.dispatch(fsm.ENERGY_OK)
    h.sm.dispatch(fsm.START_PI)
    assert h.sm.state == 'NoPiComms' and h.pi.value() == 1
    assert h.events[-1] == "pi_power_on"


def test_main_power_loss_during_shutdown_cuts_at_once():
    h = running_pi()
    h.sm.dispatch(fsm.BATTERY_LOW)
    h.sm.dispatch(fsm.MAIN_POWER_DOWN)
    assert h.sm.state == 'Monitor' and h.pi.value() == 0
    assert h.events[-1] == "pi_power_cut"


def test_without_a_shutdown_hook_power_is_cut_after_a_wait():
    h = Harness(pi_on=True)
    h.sm.request_pi_shutdown_ = None
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.STOP_PI)
    assert [ms for ms, _ in h.scheduled] == [fsm.PI_SHUTDOWN_WAIT_MS]
    h.run_scheduled()
    assert h.sm.state == 'AwaitPower' and h.pi.value() == 0


def test_deliberate_power_changes_are_recorded_and_startup_records_nothing():
    h = Harness(pi_on=False)
    assert h.recorded == []
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.ENERGY_OK)
    h.sm.dispatch(fsm.START_PI)
    h.sm.dispatch(fsm.PI_HEARTBEAT)
    h.sm.dispatch(fsm.STOP_PI)
    h.sm.dispatch(fsm.PI_STOPPED)
    h.sm.dispatch(fsm.MAIN_POWER_DOWN)
    assert h.recorded == [True, False, False]


def test_cold_start_waits_for_energy_before_starting_pi():
    # boot.py leaves the Pi off after a power-on reset; a few watts of dawn
    # sun must not be enough to start it.
    h = Harness(pi_on=False)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    for _ in range(3):
        h.sm.dispatch(fsm.ENERGY_LOW)
        h.sm.dispatch(fsm.START_PI)
    assert h.sm.state == 'AwaitPower'
    assert h.pi.value() == 0
