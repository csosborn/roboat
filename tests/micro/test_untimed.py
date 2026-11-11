import json

from untimed import Untimed


def status(**fields):
    msg = {"offset_s": 0, "src": "status"}
    msg.update(fields)
    return msg


def test_nothing_released_while_time_unknown():
    u = Untimed()
    u.hold(status(uptime_s=1), 1000)
    assert u.release(None, 2000) == []
    assert u.held == 1


def test_released_records_are_stamped_back_from_now():
    u = Untimed()
    u.hold(status(event="boot"), 1000)
    u.hold({"offset_s": 0, "src": "ina260", "logic_p": 0.4}, 61000)
    utc_now = 1794273874000
    out = u.release(utc_now, 135000)
    assert [m["utc_ms"] for m in out] == [utc_now - 134000, utc_now - 74000]
    assert out[0]["event"] == "boot"
    assert out[1]["logic_p"] == 0.4
    assert u.held == 0
    assert u.release(utc_now, 136000) == []


def test_records_are_copies():
    u = Untimed()
    msg = status(uptime_s=1)
    u.hold(msg, 0)
    out = u.release(1000, 0)
    assert "utc_ms" not in msg
    assert out[0] is not msg


def test_full_drops_oldest_non_event_first():
    one = len(json.dumps(status(n=0)))
    u = Untimed(limit_bytes=3 * one + 20)  # an event and two others
    u.hold(status(n=0, event="b"), 0)
    for i in range(1, 5):
        u.hold(status(n=i), i)
    out = u.release(10000, 10)
    # The event survives; of the rest, only the newest fit.
    assert out[0]["event"] == "b"
    assert [m["n"] for m in out[1:]] == [3, 4]
    assert u.dropped == 2


def test_full_of_events_drops_oldest():
    one = len(json.dumps(status(event="x", n=0)))
    u = Untimed(limit_bytes=2 * one)
    for i in range(3):
        u.hold(status(event="x", n=i), i)
    assert [m["n"] for m in u.release(0, 0)] == [1, 2]
    assert u.dropped == 1


def test_delivered_forgets_recent_records():
    u = Untimed()
    u.hold(status(n=0), 1000)
    u.hold(status(n=1), 5000)
    u.hold(status(event="boot", n=2), 9000)
    u.delivered(5000)
    assert [m["n"] for m in u.release(0, 9000)] == [0]
    assert u.dropped == 0
