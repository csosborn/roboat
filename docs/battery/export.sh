#!/bin/bash
# Exports battery telemetry from the Pi's InfluxDB as one CSV row per minute.
#   docs/battery/export.sh START STOP > out.csv     (RFC 3339 UTC, e.g. 2026-10-11T16:00:00Z)
# The InfluxDB token is read on the Pi and never leaves it.
set -euo pipefail
start=${1:?start time}; stop=${2:?stop time}
flux='from(bucket: "roboat_01")
  |> range(start: '"$start"', stop: '"$stop"')
  |> filter(fn: (r) => (r._measurement == "mppt" and contains(value: r._field, set: ["batt_v", "batt_i", "load_i", "solar_p", "load_on", "tracker_mode"]))
                    or (r._measurement == "ina260" and contains(value: r._field, set: ["batt_v", "logic_p"])))
  |> map(fn: (r) => ({r with _value: float(v: r._value), _field: r._measurement + "_" + r._field}))
  |> group(columns: ["_field"])
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["_time", "mppt_batt_v", "mppt_batt_i", "mppt_load_i", "mppt_solar_p", "mppt_load_on", "mppt_tracker_mode", "ina260_batt_v", "ina260_logic_p"])'
ssh -o BatchMode=yes roboat1 'TOKEN=$(grep -oP "^INFLUX_TOKEN=\K.*" ~/roboat/src/pi/monitor/monitor.env)
curl -sf -H "Authorization: Token $TOKEN" -H "Content-Type: application/vnd.flux" -H "Accept: application/csv" \
  "http://localhost:8086/api/v2/query?org=CSO" --data-binary @-' <<<"$flux" \
  | tr -d '\r' | cut -d, -f4- | grep -v '^$' | python3 -c '
import csv, sys
cols = ["_time", "mppt_batt_v", "mppt_batt_i", "mppt_load_i", "mppt_solar_p", "mppt_load_on", "mppt_tracker_mode", "ina260_batt_v", "ina260_logic_p"]
names = ["time_utc", "batt_v", "batt_i", "load_i", "solar_w", "load_on", "tracker_mode", "load_bus_v", "logic_w"]
w = csv.writer(sys.stdout, lineterminator="\n"); w.writerow(names)
for r in sorted(csv.DictReader(sys.stdin), key=lambda r: r["_time"]):  # pivot output is not in time order
    out = [r["_time"][:19] + "Z"]
    for c in cols[1:]:
        v = r.get(c, "")
        out.append("" if v == "" else ("%d" % round(float(v)) if c in ("mppt_load_on", "mppt_tracker_mode") else "%.3f" % float(v)))
    w.writerow(out)'
