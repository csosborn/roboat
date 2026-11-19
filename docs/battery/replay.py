"""Runs exported telemetry through the firmware's state-of-charge model.

    python3 docs/battery/replay.py CSV [CSV ...] [--every MIN] [--reset "MM-DD HH:MM" ...]

The CSVs come from export.sh (one row per minute). Times are local. --reset
simulates the RP2040 restarting at that time: the model is rebuilt from what
it last saved, as on the board. --fresh starts with no saved state at all.
"""
import argparse
import csv
import datetime
import os
import sys
import tempfile
import time

time.ticks_diff = lambda a, b: a - b
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "micro"))
import soc_model  # noqa: E402


def load(paths):
    rows = {}
    for path in paths:
        for r in csv.DictReader(open(path)):
            if not r["batt_v"] or not r["batt_i"]:
                continue
            t = datetime.datetime.fromisoformat(r["time_utc"].replace("Z", "+00:00"))
            bus = float(r["load_bus_v"]) if r.get("load_bus_v") else 0.0
            logic = None
            if r.get("logic_w") and bus > 9:
                logic = float(r["logic_w"]) / bus
            rows[t] = (float(r["batt_v"]), float(r["batt_i"]), float(r["solar_w"] or 0), logic)
    return sorted(rows.items())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", nargs="+")
    p.add_argument("--every", type=int, default=60, help="minutes per output row")
    p.add_argument("--reset", action="append", default=[], help="local MM-DD HH:MM")
    p.add_argument("--from", dest="start", default="")
    a = p.parse_args()

    label = lambda t: t.astimezone().strftime("%m-%d %H:%M")
    store = os.path.join(tempfile.mkdtemp(), "soc.json")
    rows = [(t, r) for t, r in load(a.csv) if label(t) >= a.start]
    t0 = rows[0][0]
    clock = {"utc": None}
    ms = lambda t: int((t - t0).total_seconds() * 1000)
    make = lambda: soc_model.SocModel(store=store, now_utc=lambda: clock["utc"])
    model = make()
    resets = set(a.reset)
    print("%-11s %7s %7s %6s %6s %6s %5s %6s %s" % (
        "local", "batt_v", "batt_i", "solar", "left", "sd", "soc", "full", "src"))
    for n, (t, (v, i, sol, logic)) in enumerate(rows):
        clock["utc"] = int(t.timestamp() * 1000)
        if label(t) in resets:
            model.save(ms(t))
            model = make()
            print("%-11s reset" % label(t))
        model.update(ms(t), v, i, sol, logic)
        if (t.hour * 60 + t.minute) % a.every == 0 or n == len(rows) - 1:
            if model.known:
                rep = model.report()
                print("%-11s %7.3f %+7.2f %6.0f %6.2f %6.2f %4.0f%% %6.2f %s" % (
                    label(t), v, i, sol, rep["cap"], rep["sd"], 100 * rep["soc"], rep["full_ah"], rep["basis"]))


if __name__ == "__main__":
    main()
