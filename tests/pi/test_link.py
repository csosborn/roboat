import json
import struct

from link import LineReader, handle, heartbeat
from timesync import ChronyRefclock, SOCK_MAGIC, encode_sample
from writer import QueuedWriter


def test_lines_split_across_reads():
    r = LineReader()
    assert r.feed(b'{"a": 1}\r\n{"b"') == ['{"a": 1}']
    assert r.feed(b': 2}\n') == ['{"b": 2}']
    assert r.feed(b'') == []


def test_heartbeat_carries_the_ack_only_once_there_is_one():
    assert json.loads(heartbeat(None)) == {"cmd": "hb"}
    assert json.loads(heartbeat(41)) == {"cmd": "hb", "ack": 41}
    assert heartbeat(41).endswith(b"\n")


def test_ack_advances_only_when_influx_accepts_the_write():
    up = [False]
    written = []

    def write(point):
        if not up[0]:
            raise ConnectionError("down")
        written.append(point)

    w = QueuedWriter(write)
    w.write("a", seq=5)
    w.write("live")
    assert w.acked_seq is None
    up[0] = True
    w.write("b", seq=6)
    assert written == ["a", "live", "b"] and w.acked_seq == 6


def test_chrony_sample_layout():
    raw = encode_sample(1791763000.25, -0.125)
    assert len(raw) == 40
    sec, usec, offset, pulse, leap, _pad, magic = struct.unpack("@qqdiiii", raw)
    assert (sec, usec, offset, pulse, leap, magic) == (1791763000, 250000, -0.125, 0, 0, SOCK_MAGIC)


def test_missing_chrony_socket_is_counted_not_fatal(tmp_path):
    clock = ChronyRefclock(str(tmp_path / "missing.sock"))
    clock.send(100.0, 100.5)
    assert clock.errors == 1 and clock.sent == 0


class FakeClock:
    def __init__(self):
        self.samples = []

    def send(self, system_time, true_time):
        self.samples.append((system_time, true_time))


def test_live_gps_feeds_the_clock_and_replays_are_acked():
    clock = FakeClock()
    w = QueuedWriter(lambda point: None)
    handle('{"src": "gps", "utc_ms": 1791763000500, "mode": 3, "sats": 7}', 1791763000.9, w, clock)
    handle('{"seq": 12, "src": "gps", "utc_ms": 1791760000000, "mode": 3, "sats": 7}',
           1791763001.0, w, clock)
    assert clock.samples == [(1791763000.9, 1791763000.5)]  # the replayed fix is old news
    assert w.acked_seq == 12


def test_points_without_gps_time_are_stamped_on_arrival():
    written = []
    w = QueuedWriter(written.append)
    handle('{"src": "ina260", "batt_v": 13.2, "logic_p": 5, "logic_i": 0.4, "logic_total_ah": 1}',
           1791763000.5, w, FakeClock())
    assert written[0]["time"] == 1791763000500000000


def test_garbage_lines_are_skipped():
    w = QueuedWriter(lambda point: None)
    handle('not json', 0.0, w, FakeClock())
    handle('[1, 2]', 0.0, w, FakeClock())
    assert not w.queue_
