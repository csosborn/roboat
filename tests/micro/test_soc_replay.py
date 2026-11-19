"""Replays recorded run-downs (docs/battery) through the state-of-charge model."""
import datetime
import os
import sys

import pytest

import soc_model as sm

BATTERY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "battery")
sys.path.insert(0, BATTERY_DIR)
from replay import load  # noqa: E402

UTC = datetime.timezone.utc


def replay(path, store, resets=()):
    rows = load([os.path.join(BATTERY_DIR, path)])
    t0 = rows[0][0]
    clock = {"utc": None}
    make = lambda: sm.SocModel(store=store, now_utc=lambda: clock["utc"])
    model = make()
    trace = []
    for t, (v, i, sol, logic) in rows:
        ms = int((t - t0).total_seconds() * 1000)
        clock["utc"] = int(t.timestamp() * 1000)
        if t in resets:
            model.save(ms)
            model = make()
        model.update(ms, v, i, sol, logic)
        if model.known:
            trace.append((t, v, model.remaining_ah, model.sd_ah, model.capacity_ah))
    return trace


def at(trace, when):
    return next(row for row in trace if row[0] >= when)


def test_november_run_down(tmp_path):
    reset = datetime.datetime(2026, 11, 14, 18, 32, tzinfo=UTC)  # a real boot that day
    trace = replay("run-down-2026-11.csv", str(tmp_path / "soc.json"), resets={reset})

    # The Pi's 12.8 V shutdown came at about 2 Ah left.
    _, v, left, sd, _ = at(trace, datetime.datetime(2026, 11, 14, 11, 0, tzinfo=UTC))
    assert left == pytest.approx(2.0, abs=0.5) and sd < 0.5

    # The reset barely matters: compare with a run that had none.
    plain = replay("run-down-2026-11.csv", str(tmp_path / "plain.json"))
    for hours in (1, 6):
        when = reset + datetime.timedelta(hours=hours)
        assert at(trace, when)[2] == pytest.approx(at(plain, when)[2], abs=0.1)

    # Empty at the Victron's 12.0 V cut-off.
    cut = next(row for row in trace if row[1] <= 12.0)
    assert cut[2] == pytest.approx(0.0, abs=0.2)

    # Capacity, learned on the way down and again on the recharge.
    assert 18.0 <= trace[-1][4] <= 18.5


def test_october_run_downs(tmp_path):
    trace = replay("discharge-2026-10.csv", str(tmp_path / "soc.json"))
    assert 18.0 <= trace[-1][4] <= 18.6
    cut = next(row for row in trace if row[1] <= 12.05)
    assert cut[2] == pytest.approx(0.0, abs=0.3)
