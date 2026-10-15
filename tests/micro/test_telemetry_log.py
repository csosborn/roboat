import json

import pytest

import telemetry_log as tl


@pytest.fixture(autouse=True)
def device_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tl, '_fs_free', lambda: None)
    return tmp_path


def msg(i):
    return {"src": "ina260", "utc_ms": 1791763000000 + i, "batt_v": 13.2}


def drain(log, now, listening=True, max_steps=10000):
    """Run replay until a pass finishes; returns the seqs sent."""
    sent = []
    for _ in range(max_steps):
        before = len(sent)
        log.step(now, listening, lambda line: sent.append(json.loads(line)["seq"]))
        now += tl.REPLAY_INTERVAL_MS
        if not log.replaying_ and len(sent) == before and sent:
            break
    return sent, now


def test_records_replay_in_order_once_the_pi_listens():
    log = tl.TelemetryLog(now_ms=0)
    for i in range(5):
        log.record(msg(i), now_ms=0)
    log.step(0, False, lambda line: pytest.fail("sent while the Pi wasn't listening"))
    sent, _ = drain(log, 0)
    assert sent == [0, 1, 2, 3, 4]


def test_replayed_lines_are_the_original_messages():
    log = tl.TelemetryLog(now_ms=0)
    log.record(msg(7), now_ms=0)
    lines = []
    log.step(0, True, lines.append)
    rec = json.loads(lines[0])
    assert rec == dict(msg(7), seq=0)


def test_no_resend_loop_while_waiting_for_acks():
    log = tl.TelemetryLog(now_ms=0)
    for i in range(3):
        log.record(msg(i), now_ms=0)
    sent, now = drain(log, 0)
    more, _ = drain(log, now, max_steps=200)  # a few seconds, less than RESEND_AFTER_MS
    assert sent == [0, 1, 2] and more == []


def test_unacknowledged_records_are_resent_after_a_while():
    log = tl.TelemetryLog(now_ms=0)
    for i in range(3):
        log.record(msg(i), now_ms=0)
    sent, now = drain(log, 0)
    log.ack(0)
    resent, _ = drain(log, now + tl.RESEND_AFTER_MS)
    assert resent == [1, 2]


def test_acks_delete_whole_segments_and_finally_everything(device_fs, monkeypatch):
    monkeypatch.setattr(tl, 'SEGMENT_BYTES', 200)
    monkeypatch.setattr(tl, 'FLUSH_BYTES', 1)  # one flush per record
    log = tl.TelemetryLog(now_ms=0)
    for i in range(10):
        log.record(msg(i), now_ms=0)
    assert len(log.segments_) > 2
    drain(log, 0)
    log.ack(4)
    assert all(first > 1 for first, _ in log.segments_[1:])
    log.ack(9)
    assert log.segments_ == [] and log.backlog == 0
    assert [p.name for p in (device_fs / 'tlm').iterdir() if p.suffix == '.jl'] == []


def test_pi_leaving_mid_replay_resends_from_the_last_ack():
    log = tl.TelemetryLog(now_ms=0)
    for i in range(10):
        log.record(msg(i), now_ms=0)
    sent = []
    now = 0
    for _ in range(4):
        log.step(now, True, lambda line: sent.append(json.loads(line)["seq"]))
        now += tl.REPLAY_INTERVAL_MS
    log.ack(1)
    log.step(now, False, lambda line: None)
    again, _ = drain(log, now)
    assert sent == [0, 1, 2, 3] and again == list(range(2, 10))


def test_sequence_numbers_and_backlog_survive_a_reset():
    log = tl.TelemetryLog(now_ms=0)
    for i in range(3):
        log.record(msg(i), now_ms=0)
    log.flush(0)
    log = tl.TelemetryLog(now_ms=0)
    assert log.next_seq_ == 3 and log.backlog == 3
    log.record(msg(3), now_ms=0)
    sent, _ = drain(log, 0)
    assert sent == [0, 1, 2, 3]


def test_sequence_numbers_never_reused_after_everything_is_acked():
    log = tl.TelemetryLog(now_ms=0)
    log.record(msg(0), now_ms=0)
    drain(log, 0)
    log.ack(0)
    log = tl.TelemetryLog(now_ms=0)
    log.record(msg(1), now_ms=0)
    sent, _ = drain(log, 0)
    assert sent == [1]


def test_stale_ack_from_before_a_reset_is_ignored():
    log = tl.TelemetryLog(now_ms=0)
    log.record(msg(0), now_ms=0)
    log.ack(500)  # beyond anything this board has issued
    assert log.backlog == 1


def test_full_log_drops_oldest_segments(monkeypatch):
    monkeypatch.setattr(tl, 'SEGMENT_BYTES', 200)
    monkeypatch.setattr(tl, 'MAX_BYTES', 600)
    monkeypatch.setattr(tl, 'FLUSH_BYTES', 1)
    log = tl.TelemetryLog(now_ms=0)
    for i in range(40):
        log.record(msg(i), now_ms=0)
    assert log.stored_bytes <= 600 + 200
    assert log.dropped > 0
    sent, _ = drain(log, 0)
    assert sent == list(range(40 - len(sent), 40))


def replay_lines(log, steps=500):
    lines = []
    for n in range(steps):
        log.step(n * tl.REPLAY_INTERVAL_MS, True, lines.append)
    return lines


def event(i, name):
    return {"src": "status", "utc_ms": 1791763000000 + i, "event": name}


def test_full_log_keeps_its_events(monkeypatch):
    monkeypatch.setattr(tl, 'SEGMENT_BYTES', 200)
    monkeypatch.setattr(tl, 'MAX_BYTES', 600)
    monkeypatch.setattr(tl, 'FLUSH_BYTES', 1)
    log = tl.TelemetryLog(now_ms=0)
    log.record(event(0, "pi_shutdown_requested"), now_ms=0)
    log.record(event(1, "pi_power_cut"), now_ms=0)
    for i in range(2, 60):
        log.record(msg(i), now_ms=0)
    assert log.dropped > 0
    lines = replay_lines(log)
    replayed = [json.loads(line) for line in lines]
    events = [r for r in replayed if "event" in r]
    assert [(r["event"], r["utc_ms"]) for r in events] == [
        ("pi_shutdown_requested", 1791763000000), ("pi_power_cut", 1791763000001)]
    assert log.dropped == 60 - len(replayed)
    assert log.stored_bytes <= 600 + 200


def test_events_survive_being_carried_over_more_than_once(monkeypatch):
    monkeypatch.setattr(tl, 'SEGMENT_BYTES', 200)
    monkeypatch.setattr(tl, 'MAX_BYTES', 600)
    monkeypatch.setattr(tl, 'FLUSH_BYTES', 1)
    log = tl.TelemetryLog(now_ms=0)
    log.record(event(0, "pi_power_cut"), now_ms=0)
    for i in range(1, 300):
        log.record(msg(i), now_ms=0)
    lines = replay_lines(log)
    assert sum('"pi_power_cut"' in line for line in lines) == 1


def test_low_free_space_drops_oldest_segments(monkeypatch):
    monkeypatch.setattr(tl, 'SEGMENT_BYTES', 200)
    monkeypatch.setattr(tl, 'FLUSH_BYTES', 1)
    log = tl.TelemetryLog(now_ms=0)
    for i in range(10):
        log.record(msg(i), now_ms=0)
    assert log.dropped == 0
    monkeypatch.setattr(tl, '_fs_free', lambda: tl.FS_RESERVE_BYTES - 1)
    log.record(msg(10), now_ms=0)
    assert len(log.segments_) == 1 and log.dropped > 0


def test_unflushed_records_are_flushed_on_schedule(device_fs):
    log = tl.TelemetryLog(now_ms=0)
    log.record(msg(0), now_ms=0)
    assert log.segments_ == []
    log.step(tl.FLUSH_MS, False, lambda line: None)
    assert len(log.segments_) == 1
