import json

import pytest

import soc_model as sm

MIN = 60000
HOUR = 60 * MIN


class Clock:
    def __init__(self, utc=None):
        self.utc = utc

    def __call__(self):
        return self.utc


def run(model, start_ms, minutes, volts, amps, panel_w=0, logic_a=None, cs=None):
    """Feed one reading a second for this many minutes; returns the end time."""
    t = start_ms
    for _ in range(minutes * 60):
        model.update(t, volts, amps, panel_w, logic_a, cs)
        t += 1000
    return t


def fill(model, t=0):
    """Absorption long enough to count as full."""
    return run(model, t, 3, 14.2, 0.3, panel_w=10)


def test_absorption_with_a_low_tail_is_full(tmp_path):
    m = sm.SocModel(store=str(tmp_path / "soc.json"))
    fill(m)
    assert m.source == "full"
    assert m.remaining_ah == pytest.approx(sm.NOMINAL_CAPACITY_AH, abs=0.01)
    assert m.soc == 1.0


def test_float_counts_as_full(tmp_path):
    m = sm.SocModel(store=str(tmp_path / "soc.json"))
    run(m, 0, 3, 13.5, 0.0, panel_w=5, cs=sm.VICTRON_FLOAT)
    assert m.source == "full"


def test_counts_charge_including_the_hidden_draw(tmp_path):
    m = sm.SocModel(store=str(tmp_path / "soc.json"))
    t = fill(m)
    q0 = m.remaining_ah
    run(m, t, 60, 13.24, -0.3)
    assert q0 - m.remaining_ah == pytest.approx(0.3 + sm.HIDDEN_DRAW_A, abs=0.002)


def test_small_currents_are_counted_exactly(tmp_path):
    # 1 mA for an hour is 1 mAh; floats near 18 Ah would lose it.
    m = sm.SocModel(store=None)
    fill(m)
    c0, q0 = m.counted_mas_, m.q_mas_
    for _ in range(3600):
        m._count(-0.001, 1000)
    assert m.counted_mas_ - c0 == -3600
    assert m.q_mas_ - q0 == -3600
    m._count(-0.0004, 1000)  # rounds to 0 mA
    m._count(-0.0006, 1000)  # rounds to 1 mA: 1 mA*s
    assert m.counted_mas_ - c0 == -3601


def test_victron_dead_band_falls_back_to_the_ina(tmp_path):
    m = sm.SocModel(store=None)
    t = fill(m)
    q0 = m.remaining_ah
    run(m, t, 60, 12.9, 0.0, logic_a=0.03)
    assert q0 - m.remaining_ah == pytest.approx(0.03 + sm.HIDDEN_DRAW_A, abs=0.002)


def test_victron_wins_when_it_sees_more_than_the_logic_side(tmp_path):
    # The ESC draws from the load output, outside the INA260.
    m = sm.SocModel(store=None)
    t = fill(m)
    q0 = m.remaining_ah
    run(m, t, 60, 12.9, -4.0, logic_a=0.3)
    assert q0 - m.remaining_ah == pytest.approx(4.0 + sm.HIDDEN_DRAW_A, abs=0.01)


def test_knee_voltage_corrects_the_count():
    m = sm.SocModel(store=None)
    t = fill(m)
    m.q_mas_ = int(8.0 * sm.MAS_PER_AH)   # count says 8 Ah, voltage says ~1.5
    t = run(m, t, 3 * 60, 12.76 - 0.03 * sm.INTERNAL_R, -0.03 + sm.HIDDEN_DRAW_A)
    assert m.source == "knee"
    assert m.remaining_ah == pytest.approx(1.5, abs=0.4)


def test_no_voltage_correction_soon_after_charging():
    m = sm.SocModel(store=None)
    t = fill(m)
    m.q_mas_ = int(8.0 * sm.MAS_PER_AH)
    run(m, t, 90, 12.76, -0.02)
    assert m.source == "full"


def test_upper_plateau_raises_a_low_estimate_but_never_lowers_a_high_one():
    m = sm.SocModel(store=None)
    t = fill(m)
    m.q_mas_ = int(15.0 * sm.MAS_PER_AH)
    t = run(m, t, 3 * 60, 13.24, -0.28)
    assert m.source == "full"            # 15 Ah is consistent with the plateau
    m.q_mas_ = int(6.0 * sm.MAS_PER_AH)
    m.landmark_ms_ = None
    # A confident count gives way over an hour of repeated readings.
    run(m, t, 60, 13.24, -0.28)
    assert m.source == "plateau"
    assert m.remaining_ah > 9.0


def test_first_guess_without_saved_state_is_wide():
    m = sm.SocModel(store=None)
    m.update(0, 13.24, -0.28, 0)
    assert m.source == "guess"
    assert m.remaining_ah >= sm.UPPER_MIN_AH
    assert m.sd_ah > 2


def test_state_survives_a_reset(tmp_path):
    path = str(tmp_path / "soc.json")
    clock = Clock(utc=1_000_000_000_000)
    m = sm.SocModel(store=path, now_utc=clock)
    t = fill(m)
    t = run(m, t, 30, 13.24, -0.3)
    clock.utc = 1_000_000_000_000 + t
    m.save(t)
    q = m.remaining_ah

    # Back up 5 minutes later, before the GPS has the time.
    clock.utc = None
    m2 = sm.SocModel(store=path, now_utc=clock)
    assert m2.source == "restored"
    assert m2.remaining_ah == pytest.approx(q, abs=0.001)
    m2.update(0, 13.24, -0.3, 0)
    # Then the time arrives: the 5 minutes down cost at least the hidden draw.
    clock.utc = 1_000_000_000_000 + t + 5 * MIN + 1000
    m2.update(1000, 13.24, -0.3, 0)
    lost = q - m2.remaining_ah
    counted = (0.3 + sm.HIDDEN_DRAW_A) / 3600   # the one second since boot
    assert lost - counted == pytest.approx(sm.HIDDEN_DRAW_A * 5 / 60, abs=0.0002)
    assert m2.sd_ah < 0.5


def test_unknown_downtime_widens_the_estimate(tmp_path):
    path = str(tmp_path / "soc.json")
    m = sm.SocModel(store=path)          # no clock: the save has no time
    fill(m)
    m.save(0)
    m2 = sm.SocModel(store=path)
    assert m2.sd_ah > 3


def test_corrupt_store_is_ignored(tmp_path):
    path = tmp_path / "soc.json"
    path.write_text("{not json")
    m = sm.SocModel(store=str(path))
    assert not m.known


def test_save_is_atomic_json(tmp_path):
    path = tmp_path / "soc.json"
    m = sm.SocModel(store=str(path))
    fill(m)
    state = json.loads(path.read_text())
    assert state["src"] == "full"
    assert not (tmp_path / "soc.json.tmp").exists()


def test_capacity_learned_from_full_to_knee():
    m = sm.SocModel(store=None)
    t = fill(m)
    # Draw 16 Ah, then sit in the knee at ~1.0 Ah: capacity looks like ~17 Ah.
    amps = -2.0
    t = run(m, t, 8 * 60 - 3, 13.1, amps + sm.HIDDEN_DRAW_A)
    before = m.capacity_ah
    run(m, t, 3 * 60, 12.71 - 0.03 * sm.INTERNAL_R, -0.03 + sm.HIDDEN_DRAW_A)
    observed = 16.0 + 0.03 * 3 + 1.0
    assert m.capacity_ah == pytest.approx(
        before + sm.CAPACITY_LEARN_WEIGHT * (observed - before), abs=0.1)


def test_report_fields():
    m = sm.SocModel(store=None)
    fill(m)
    r = m.report()
    assert set(r) == {"soc", "cap", "cap_min", "cap_max", "sd", "full_ah", "basis"}
    assert r["cap_min"] <= r["cap"] <= r["cap_max"]


def test_knee_lookup_ends():
    assert sm.knee_lookup(13.2) is None
    assert sm.knee_lookup(11.5)[0] == 0.0
    ah, sd = sm.knee_lookup(12.71)
    assert ah == pytest.approx(1.0)
