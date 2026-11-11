import json

from untimed import Untimed, HOLD_MS


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
    out = u.release(1000, HOLD_MS)
    assert "utc_ms" not in msg
    assert out[0] is not msg


def test_full_drops_oldest_non_event_first():
    one = len(json.dumps(status(n=0)))
    u = Untimed(limit_bytes=3 * one + 20)  # an event and two others
    u.hold(status(n=0, event="b"), 0)
    for i in range(1, 5):
        u.hold(status(n=i), i)
    out = u.release(10000, 10 + HOLD_MS)
    # The event survives; of the rest, only the newest fit.
    assert out[0]["event"] == "b"
    assert [m["n"] for m in out[1:]] == [3, 4]
    assert u.dropped == 2


def test_full_of_events_drops_oldest():
    one = len(json.dumps(status(event="x", n=0)))
    u = Untimed(limit_bytes=2 * one)
    for i in range(3):
        u.hold(status(event="x", n=i), i)
    assert [m["n"] for m in u.release(0, 2 + HOLD_MS)] == [1, 2]
    assert u.dropped == 1


def test_records_are_held_a_while_even_once_time_is_known():
    u = Untimed()
    u.hold(status(n=0), 0)
    u.hold(status(n=1), 2000)
    assert u.release(1000, 1000) == []
    assert [m["n"] for m in u.release(1000, HOLD_MS)] == [0]
    assert u.held == 1
    assert [m["n"] for m in u.release(1000, 2000 + HOLD_MS)] == [1]


def test_pi_heard_soon_after_a_record_had_it_live():
    # A watchdog reset with the Pi up: the boot event goes out before its first
    # heartbeat arrives, and a quick GPS fix comes in between.
    u = Untimed()
    u.hold(status(n=0), 1000)
    u.hold(status(event="boot", n=1), 10000)
    assert [m["n"] for m in u.release(5000, 11500)] == [0]
    u.delivered(12000)
    assert u.held == 0
    assert u.release(5000, 20000) == []
    assert u.dropped == 0


def test_delivered_keeps_older_records():
    u = Untimed()
    u.hold(status(n=0), 1000)
    u.hold(status(n=1), 9000)
    u.delivered(9000 + HOLD_MS - 1)
    assert [m["n"] for m in u.release(0, 20000)] == [0]
