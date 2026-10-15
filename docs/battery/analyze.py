"""Summarizes a battery telemetry CSV from export.sh.

    python3 docs/battery/analyze.py CSV [--from "MM-DD HH:MM"] [--to "MM-DD HH:MM"] [--every MIN]

Times are local. Charge is counted from the Victron's battery current (positive
is charging), starting at --from. Gaps in the data (for example while nothing
was being recorded) are bridged at the current that follows them.
"""
import argparse
import csv
import datetime


def load(path):
    rows = []
    for r in csv.DictReader(open(path)):
        t = datetime.datetime.fromisoformat(r.pop("time_utc").replace("Z", "+00:00")).astimezone()
        rows.append((t, {k: float(v) for k, v in r.items() if v != ""}))
    return sorted(rows, key=lambda row: row[0])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--from", dest="start", default="")
    p.add_argument("--to", dest="stop", default="99")
    p.add_argument("--every", type=int, default=60, help="minutes per output row")
    a = p.parse_args()
    label = lambda t: t.strftime("%m-%d %H:%M")
    rows = [(t, r) for t, r in load(a.csv) if a.start <= label(t) <= a.stop]

    ah, last = 0.0, None
    print("%-12s %7s %7s %7s %6s %4s %8s %7s" % (
        "local", "batt_v", "bus_v", "batt_i", "sol_w", "load", "net_Ah", "mV/Ah"))
    prev = None
    for n, (t, r) in enumerate(rows):
        if "batt_i" in r:
            if last is not None:
                ah += r["batt_i"] * (t - last).total_seconds() / 3600
            last = t
        if (t.hour * 60 + t.minute) % a.every == 0 or n == len(rows) - 1:
            v = r.get("batt_v", float("nan"))
            slope = ""
            if prev is not None and abs(ah - prev[1]) > 0.01:
                slope = "%7.0f" % (1000 * (v - prev[0]) / (ah - prev[1]))
            print("%-12s %7.3f %7.3f %+7.2f %6.0f %4s %+8.2f %7s" % (
                label(t), v, r.get("load_bus_v", float("nan")), r.get("batt_i", float("nan")),
                r.get("solar_w", float("nan")), "%d" % r["load_on"] if "load_on" in r else "-", ah, slope))
            prev = (v, ah)


if __name__ == "__main__":
    main()
