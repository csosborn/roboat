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
        self.sm = fsm.RoboatSM(FakeNeoPixel(), self.pi, self.drive, FakePWM(),
                               schedule=lambda ms, fn: self.scheduled.append((ms, fn)),
                               on_pi_power_on=self._powered_on,
                               record_pi_power=self.recorded.append)

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


def test_requested_shutdown_cuts_power_after_wait():
    h = Harness(pi_on=True)
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.PI_HEARTBEAT)
    h.sm.dispatch(fsm.STOP_PI)
    assert h.sm.state == 'PiStopping'
    assert h.pi.value() == 1
    assert [ms for ms, _ in h.scheduled] == [fsm.PI_SHUTDOWN_WAIT_MS]
    h.run_scheduled()
    assert h.sm.state == 'PiOff'
    assert h.pi.value() == 0


def test_deliberate_power_changes_are_recorded_and_startup_records_nothing():
    h = Harness(pi_on=False)
    assert h.recorded == []
    h.sm.dispatch(fsm.MAIN_POWER_UP)
    h.sm.dispatch(fsm.ENERGY_OK)
    h.sm.dispatch(fsm.START_PI)
    h.sm.dispatch(fsm.PI_HEARTBEAT)
    h.sm.dispatch(fsm.STOP_PI)
    h.run_scheduled()
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
