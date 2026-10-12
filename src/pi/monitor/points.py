"""Turns RP2040 telemetry messages into InfluxDB points.

When a message carries utc_ms (the RP2040's GPS-disciplined clock), the point
is timestamped with it. Otherwise InfluxDB stamps it on arrival with the Pi's
clock, which may be wrong after a boot until it syncs.
"""

ENVELOPE = ("src", "offset_s", "utc_ms", "seq")


def _status(m):
    return {k: v for k, v in m.items() if k not in ENVELOPE}


def _mppt(m):
    return {
        "solar_v": m["sol_v"],
        "solar_p": m["sol_p"],
        "tracker_mode": int(m["mppt_mode"]),
        "epoch": m["mppt_epoch"],
        "load_i": m["load_i"],
        "batt_v": m["batt_v"],
        "batt_i": m["batt_i"],
        "total_energy": m["mppt_total_kwh"],
    }


def _ina260(m):
    return {
        "logic_p": m["logic_p"],
        "logic_i": m["logic_i"],
        "batt_v": m["batt_v"],
        "logic_total_ah": m["logic_total_ah"],
    }


def _battery(m):
    return {
        "cap_ah": m["cap"],
        "cap_ah_max": m["cap_max"],
        "cap_ah_min": m["cap_min"],
        "soc": float(m["soc"]),
    }


def _gps(m):
    # Field names and types match what the monitor wrote when gpsd was the source.
    fields = {"error": int(m.get("error", 0)), "mode": int(m["mode"]), "sats": int(m["sats"])}
    if "lat_e7" in m and "lon_e7" in m:
        fields["lat"] = m["lat_e7"] / 1e7
        fields["lon"] = m["lon_e7"] / 1e7
    for key in ("hspeed", "track", "alt"):
        if key in m:
            fields[key] = float(m[key])
    if "time" in m:
        fields["time"] = m["time"]
    return fields


MEASUREMENTS = {
    "status": ("rp2040_status", _status),
    "mppt": ("mppt", _mppt),
    "ina260": ("ina260", _ina260),
    "battery": ("battery", _battery),
    "gps": ("gps", _gps),
}


def to_point(message):
    """Returns an InfluxDB point dict, or None for an unrecognised source."""
    entry = MEASUREMENTS.get(message.get("src"))
    if entry is None:
        return None
    measurement, fields = entry
    point = {"measurement": measurement, "fields": fields(message)}
    utc_ms = message.get("utc_ms")
    if isinstance(utc_ms, int):
        point["time"] = utc_ms * 1000000
    return point
