from points import to_point


def test_gps_message_keeps_the_gpsd_era_fields_and_types():
    p = to_point({"src": "gps", "offset_s": 0, "utc_ms": 1791752678250, "error": 0,
                  "mode": 3, "sats": 8, "lat_e7": 377749000, "lon_e7": -1224194000,
                  "hspeed": 1.0, "track": 87, "alt": 12.3, "time": "2026-10-11T19:04:38.250Z"})
    assert p["measurement"] == "gps"
    assert p["time"] == 1791752678250 * 1000000
    f = p["fields"]
    assert f["lat"] == 37.7749 and f["lon"] == -122.4194
    assert isinstance(f["mode"], int) and isinstance(f["track"], float)
    assert f["time"] == "2026-10-11T19:04:38.250Z"


def test_gps_without_fix_has_no_position():
    p = to_point({"src": "gps", "error": 0, "mode": 1, "sats": 0})
    assert "lat" not in p["fields"] and "time" not in p


def test_status_drops_the_envelope():
    p = to_point({"src": "status", "offset_s": 0, "utc_ms": 5, "version": "abc", "boot": 1})
    assert p["fields"] == {"version": "abc", "boot": 1}
    assert p["time"] == 5000000


def test_unknown_source_ignored():
    assert to_point({"src": "nope"}) is None
    assert to_point({}) is None
