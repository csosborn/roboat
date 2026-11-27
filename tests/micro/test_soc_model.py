import json
import math

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
    assert m.soc == pytest.approx(1.0, abs=0.001)   # the top limit trims a hair


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


def test_the_ina_counts_when_the_victron_reads_only_a_little_more(tmp_path):
    # The Victron's offset drifts by tens of mA; the INA260 is the better
    # measure of the same load.
    m = sm.SocModel(store=None)
    t = fill(m)
    q0 = m.remaining_ah
    run(m, t, 60, 13.0, -0.31, logic_a=0.29)
    assert q0 - m.remaining_ah == pytest.approx(0.29 + sm.HIDDEN_DRAW_A, abs=0.002)


def test_charging_is_scaled_for_the_victrons_low_reading(tmp_path):
    m = sm.SocModel(store=None)
    t = fill(m)
    m.q_mas_ = int(5.0 * sm.MAS_PER_AH)
    run(m, t, 60, 13.6, 2.0, panel_w=30)
    assert m.remaining_ah == pytest.approx(5.0 + 2.0 * sm.CHARGE_GAIN, abs=0.002)


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
    m.q_mas_ = int(8.0 * sm.MAS_PER_AH)   # count says 8 Ah, voltage says ~1.8
    t = run(m, t, 3 * 60, 12.76 - 0.03 * sm.INTERNAL_R, -0.03 + sm.HIDDEN_DRAW_A)
    assert m.source == "knee"
    assert m.remaining_ah == pytest.approx(1.8, abs=0.4)


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
    assert m2.mean_ah == pytest.approx(q, abs=0.001)   # before the limits' trim
    m2.update(0, 13.24, -0.3, 0)
    # Then the time arrives: the 5 minutes down cost at least the hidden draw.
    clock.utc = 1_000_000_000_000 + t + 5 * MIN + 1000
    m2.update(1000, 13.24, -0.3, 0)
    lost = q - m2.mean_ah   # the gap's shift, before the ceiling's trim
    counted = (0.3 + sm.HIDDEN_DRAW_A) / 3600   # the one second since boot
    assert lost - counted == pytest.approx(sm.HIDDEN_DRAW_A * 5 / 60, abs=0.0002)
    assert m2.sd_ah < 0.5


def test_a_second_reset_before_the_clock_comes_back_to_the_timed_save(tmp_path):
    path = str(tmp_path / "soc.json")
    clock = Clock(utc=1_000_000_000_000)
    m = sm.SocModel(store=path, now_utc=clock)
    t = fill(m)
    t = run(m, t, 30, 13.24, -0.3)
    clock.utc = 1_000_000_000_000 + t
    m.save(t)
    q = m.remaining_ah

    # Reset; runs two minutes without the time, then resets again.
    clock.utc = None
    m2 = sm.SocModel(store=path, now_utc=clock)
    run(m2, 0, 2, 13.24, -0.3)
    assert json.loads(open(path).read())["t"] is not None
    m3 = sm.SocModel(store=path, now_utc=clock)
    assert m3.mean_ah == pytest.approx(q, abs=0.001)
    assert m3.sd_ah < 1.0

    # The time arrives: the whole gap since the save is settled, and saved.
    clock.utc = 1_000_000_000_000 + t + 10 * MIN
    m3.update(0, 13.24, -0.3, 0)
    assert q - m3.mean_ah == pytest.approx(sm.HIDDEN_DRAW_A * 10 / 60, abs=0.001)
    assert json.loads(open(path).read())["t"] == clock.utc


def test_full_settles_an_unknown_gap(tmp_path):
    path = str(tmp_path / "soc.json")
    clock = Clock(utc=1_000_000_000_000)
    m = sm.SocModel(store=path, now_utc=clock)
    fill(m)
    m.save(0)
    clock.utc = None
    m2 = sm.SocModel(store=path, now_utc=clock)
    fill(m2)
    assert m2.sd_ah == pytest.approx(0.15, abs=0.01)
    assert json.loads(open(path).read())["src"] == "full"


def test_unknown_downtime_widens_the_estimate_downward_only(tmp_path):
    path = str(tmp_path / "soc.json")
    m = sm.SocModel(store=path)          # no clock: the save has no time
    fill(m)
    m.save(0)
    m2 = sm.SocModel(store=path)
    assert m2.sd_ah > 2
    assert m2.remaining_ah < sm.NOMINAL_CAPACITY_AH - 2
    assert m2.report()["cap_max"] <= sm.NOMINAL_CAPACITY_AH


def test_learned_capacity_survives_a_reset(tmp_path):
    path = str(tmp_path / "soc.json")
    m = sm.SocModel(store=path)
    fill(m)
    m.capacity_ah = 18.6
    m.save(0)
    assert sm.SocModel(store=path).capacity_ah == pytest.approx(18.6)


def test_capacity_from_an_older_store_version_is_dropped(tmp_path):
    # The charge left carries over; a capacity learned with the old counting
    # doesn't.
    path = tmp_path / "soc.json"
    path.write_text(json.dumps({"q": 9 * sm.MAS_PER_AH, "var": 0.04, "cap": 18.3,
                                "src": "knee", "t": None}))
    m = sm.SocModel(store=str(path))
    assert m.mean_ah == pytest.approx(9.0)
    assert m.capacity_ah == sm.NOMINAL_CAPACITY_AH


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


# -- hard limits ----------------------------------------------------------------

def reference_cut(mean, sd, lo, hi, n=200000):
    """Moments of a cut normal by brute-force integration."""
    lo = mean - 12 * sd if lo is None else lo
    hi = mean + 12 * sd if hi is None else hi
    step = (hi - lo) / n
    w = m1 = m2 = 0.0
    for k in range(n):
        x = lo + (k + 0.5) * step
        p = math.exp(-0.5 * ((x - mean) / sd) ** 2)
        w += p
        m1 += p * x
        m2 += p * x * x
    mu = m1 / w
    return mu, (m2 / w - mu * mu) ** 0.5


@pytest.mark.parametrize("mean,sd,lo,hi", [
    (5.0, 5.9, 0.0, None),       # the 11-27 estimate, cut at empty
    (-0.5, 5.6, -0.15, 1.0),     # a long downtime, both limits
    (19.0, 3.6, None, 20.0),     # a ceiling just above the mean
    (-6.0, 1.0, 0.0, None),      # nearly all of it below the floor
    (2.0, 0.2, 0.0, 19.0),       # limits far away change nothing
])
def test_cut_to_matches_integration(mean, sd, lo, hi):
    got = sm.cut_to(mean, sd, lo, hi)
    want = reference_cut(mean, sd, lo, hi)
    assert got[0] == pytest.approx(want[0], abs=0.01)
    assert got[1] == pytest.approx(want[1], abs=0.01)


def test_cut_to_far_beyond_a_limit_sits_just_inside_it():
    m, s = sm.cut_to(-60.0, 1.0, 0.0, None)
    assert 0.0 <= m < 0.05 and s < 0.05


EMPTY = int(sm.EMPTY_LIMIT_AH * sm.MAS_PER_AH)


def wide(model, ah, sd):
    model.q_mas_ = int(ah * sm.MAS_PER_AH)
    model.var_ = sd * sd


def settle_load(model, t, ah, sd):
    """Ten minutes of discharge with the load output on, then set the estimate."""
    for _ in range(sm.FLOOR_SETTLE_MS // 1000 + 1):
        model.update(t, 13.0, -0.3, 0, 0.28, None, True)
        t += 1000
    wide(model, ah, sd)
    model.update(t, 13.0, -0.3, 0, 0.28, None, True)
    return t + 1000


def test_load_on_sets_a_floor_that_charging_carries_up():
    m = sm.SocModel(store=None)
    t = fill(m)
    t = settle_load(m, t, 1.0, 5.0)
    # Cut at the floor: the mean rises, the spread shrinks, the Gaussian stays.
    assert m.remaining_ah > 3.5 and m.sd_ah < 3.5
    assert m.mean_ah == pytest.approx(1.0, abs=0.01)
    # An amp-hour of charging lifts the floor, and the minimum, with it.
    for _ in range(1800):
        m.update(t, 13.4, 2.0 / sm.CHARGE_GAIN, 30, 0.28, None, True)
        t += 1000
    assert m.report()["cap_min"] > 0.8


def test_a_floor_held_for_hours_is_not_counted_again_and_again():
    m = sm.SocModel(store=None)
    t = fill(m)
    t = settle_load(m, t, 1.0, 5.0)
    first = m.remaining_ah - m.mean_ah
    run_load = lambda t, minutes: [m.update(t + k * 1000, 13.0, -0.0, 0, 0.0, None, True)
                                   for k in range(minutes * 60)]
    run_load(t, 90)   # short of QUIET_MS, so no voltage landmark
    # Over an hour and a half of the same evidence: the cut is no deeper
    # than at first, beyond the hidden draw's small shift.
    assert m.remaining_ah - m.mean_ah == pytest.approx(first, abs=0.1)


def test_load_off_sets_no_floor():
    m = sm.SocModel(store=None)
    t = fill(m)
    run(m, t, 15, 12.0, 0.0)
    assert m.floor_mas_ < int(sm.LOAD_ON_FLOOR_AH * sm.MAS_PER_AH)   # only the empty limit


def test_the_floor_waits_for_a_settled_discharge():
    # A rested battery's voltage recovers, and the load comes on at power-up.
    m = sm.SocModel(store=None)
    t = fill(m)
    for _ in range(9 * 60):
        m.update(t, 13.0, -0.3, 0, 0.28, None, True)
        t += 1000
    assert m.floor_mas_ == EMPTY
    m.update(t, 13.4, 2.0, 30, 0.28, None, True)     # charging restarts the wait
    t += 1000
    for _ in range(9 * 60):
        m.update(t, 13.0, -0.3, 0, 0.28, None, True)
        t += 1000
    floor = m.floor_mas_                              # the empty limit, carried up
    assert floor < int(sm.LOAD_ON_FLOOR_AH * sm.MAS_PER_AH)
    for _ in range(61):
        m.update(t, 13.0, -0.3, 0, 0.28, None, True)
        t += 1000
    assert m.floor_mas_ == int(sm.LOAD_ON_FLOOR_AH * sm.MAS_PER_AH)


def test_with_no_floor_the_estimate_is_still_cut_at_empty():
    m = sm.SocModel(store=None)
    fill(m)
    wide(m, -0.5, 5.0)
    assert m.remaining_ah > 3
    assert m.report()["cap_min"] >= 0.0


def test_after_a_long_downtime_at_empty_the_estimate_stays_near_empty(tmp_path):
    # 2026-11-25..27: run down to the cut-off, board off for ~37 h, then
    # charging from the moment it came back.
    path = str(tmp_path / "soc.json")
    clock = Clock(utc=1_000_000_000_000)
    m = sm.SocModel(store=path, now_utc=clock)
    t = fill(m)
    wide(m, 0.0, 0.08)
    m.save(t)
    clock.utc += 37 * HOUR
    m2 = sm.SocModel(store=path, now_utc=clock)
    t = 0
    m2.update(t, 13.1, 3.5, 50, 0.3, None, True)
    t += 1000
    # Between the empty limit and the ceiling the saved state sets.
    assert 0.0 <= m2.remaining_ah < 0.6
    assert m2.sd_ah < 0.6
    assert m2.var_ ** 0.5 > 5        # the Gaussian alone is still wide
    # 2.5 h of charging at 3.5 A, then 8 h of discharge at 0.3 A.
    for _ in range(150 * 60):
        m2.update(t, 13.4, 3.5, 50, 0.3, None, True)
        t += 1000
    for _ in range(8 * 60 * 60):
        clock.utc += 1000
        m2.update(t, 13.08, -0.31, 0, 0.29, None, True)
        t += 1000
    want = 2.5 * 3.5 * sm.CHARGE_GAIN - 8 * (0.29 + sm.HIDDEN_DRAW_A)
    assert m2.remaining_ah == pytest.approx(want, abs=0.6)
    r = m2.report()
    assert r["cap_max"] - r["cap_min"] < 1.5


def test_full_drops_the_ceiling(tmp_path):
    path = str(tmp_path / "soc.json")
    m = sm.SocModel(store=path)
    t = fill(m)
    wide(m, 2.0, 0.1)
    m.save(t)
    m2 = sm.SocModel(store=path)
    assert m2.ceiling_mas_ is not None
    fill(m2)
    assert m2.ceiling_mas_ is None
    assert m2.remaining_ah == pytest.approx(m2.capacity_ah, abs=0.01)


def test_a_landmark_far_above_the_ceiling_drops_it(tmp_path):
    # Charged while the board was down, against expectation.
    path = str(tmp_path / "soc.json")
    clock = Clock(utc=1_000_000_000_000)
    m = sm.SocModel(store=path, now_utc=clock)
    t = fill(m)
    wide(m, 1.0, 0.1)
    m.save(t)
    clock.utc += 10 * HOUR
    m2 = sm.SocModel(store=path, now_utc=clock)
    run(m2, 0, 3 * 60, 13.30, -0.28, logic_a=0.26)   # the upper plateau
    assert m2.ceiling_mas_ is None
    assert m2.remaining_ah > 9


def test_above_the_knee_at_least_its_top_is_left():
    m = sm.SocModel(store=None)
    t = fill(m)
    wide(m, 3.0, 0.5)
    run(m, t, 3 * 60, 13.10, -0.28, logic_a=0.26)    # the lower plateau
    assert m.source == "plateau"
    assert m.remaining_ah > 3.5


def test_a_gap_in_readings_drops_the_limits():
    m = sm.SocModel(store=None)
    t = fill(m)
    t = settle_load(m, t, 1.0, 1.0)
    assert m.floor_mas_ is not None
    m.ceiling_mas_ = int(2.0 * sm.MAS_PER_AH)
    m.update(t + 5 * MIN, 13.0, -0.3, 0, 0.28, None, None)
    assert m.floor_mas_ == EMPTY and m.ceiling_mas_ is None


def test_a_long_absorption_never_lifts_the_estimate_past_full():
    m = sm.SocModel(store=None)
    t = run(m, 0, 1, 13.3, -0.3)
    wide(m, 10.0, 5.0)
    t = run(m, t, 4 * 60, 14.2, 3.0, panel_w=50)     # a high tail: never "full"
    assert m.floor_mas_ <= int(m.capacity_ah * sm.MAS_PER_AH)
    assert m.remaining_ah <= m.capacity_ah + 0.01
    assert m.soc <= 1.0
