import pytest

import power_policy as pp


@pytest.fixture(autouse=True)
def device_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("last_choice", [None, 0, 1])
def test_cold_start_keeps_pi_off(last_choice):
    assert pp.pi_power_at_boot(cold_start=True, pin_driven=False, last_choice=last_choice) == 0


@pytest.mark.parametrize("last_choice,expected", [(None, 1), (0, 0), (1, 1)])
def test_watchdog_reset_restores_last_deliberate_choice(last_choice, expected):
    assert pp.pi_power_at_boot(cold_start=False, pin_driven=False,
                               last_choice=last_choice) == expected


@pytest.mark.parametrize("cold_start", [True, False])
def test_soft_reset_leaves_pin_alone(cold_start):
    # After a soft reset the hard-reset cause is stale, so it must not matter.
    assert pp.pi_power_at_boot(cold_start=cold_start, pin_driven=True, last_choice=0) is None


def test_recorder_round_trip_and_writes_only_on_change(device_fs):
    assert pp.read_last_choice() is None
    record = pp.ChoiceRecorder()
    record(True)
    assert pp.read_last_choice() == 1
    mtime = (device_fs / pp.PI_POWER_FILE).stat().st_mtime_ns
    record(True)
    assert (device_fs / pp.PI_POWER_FILE).stat().st_mtime_ns == mtime
    record(False)
    assert pp.read_last_choice() == 0


def test_corrupt_choice_file_reads_as_unknown(device_fs):
    (device_fs / pp.PI_POWER_FILE).write_text("x")
    assert pp.read_last_choice() is None
