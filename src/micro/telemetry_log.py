"""Stores telemetry on flash while the Pi isn't listening, and replays it later.

Records are JSON lines in segment files under tlm/, each named after the
sequence number of its first record, with "seq" as the first key of every
record. The Pi acknowledges cumulatively by sequence number; a segment is
deleted only once every record in it has been acknowledged. Sequence numbers
persist across resets (tlm/next), so an acknowledgement can never match a
newer record. Replaying a record twice is harmless: InfluxDB keeps one point
per series and timestamp.

When the log is full, the oldest segment goes, except for its event records
(status records with an "event" field), which are recorded again at the end.
They keep their original utc_ms, so InfluxDB still files them in time order.
"""
import json
import os
import time

LOG_DIR = 'tlm'
NEXT_FILE = LOG_DIR + '/next'
SEGMENT_BYTES = 16384
MAX_BYTES = 4 * 1024 * 1024
# Free flash always left for a deploy to stage new firmware.
FS_RESERVE_BYTES = 1024 * 1024
FLUSH_MS = 30000
FLUSH_BYTES = 4096
REPLAY_INTERVAL_MS = 30
REPLAY_BATCH = 8
# After a replay pass, wait this long for acknowledgements before resending.
RESEND_AFTER_MS = 60000


def _seq_of(line):
    # Every record starts '{"seq": N, ...'.
    return int(line[8:line.index(',')])


def _is_event(line):
    return '"event": ' in line


def _fs_free():
    try:
        st = os.statvfs(LOG_DIR)
        return st[0] * st[4]
    except OSError:
        return None


class TelemetryLog:

    def __init__(self, now_ms):
        try:
            os.mkdir(LOG_DIR)
        except OSError:
            pass
        self.segments_ = self._scan()          # [[first_seq, bytes], ...] oldest first
        self.next_seq_ = self._load_next_seq()
        self.pending_ = []                     # encoded lines not yet on flash
        self.pending_bytes_ = 0
        self.last_flush_ms_ = now_ms
        self.acked_ = -1
        self.replaying_ = False
        self.cursor_ = None                    # (segment first_seq, byte offset)
        self.batch_ = []
        self.next_send_ms_ = now_ms
        self.last_sent_ = -1                   # highest seq sent in a finished pass
        self.pass_end_ms_ = now_ms
        self.recorded = 0
        self.dropped = 0
        self.replayed = 0

    # --- recording ---------------------------------------------------------

    def record(self, message, now_ms):
        self._append(message)
        self.recorded += 1
        if self.pending_bytes_ >= FLUSH_BYTES:
            self.flush(now_ms)

    def flush(self, now_ms):
        self.last_flush_ms_ = now_ms
        if not self.pending_:
            return
        self._write_pending()
        self._enforce_limit()

    def _append(self, message):
        line = '{{"seq": {}, {}\n'.format(self.next_seq_, json.dumps(message)[1:])
        self.next_seq_ += 1
        self.pending_.append(line)
        self.pending_bytes_ += len(line)

    def _write_pending(self):
        if not self.segments_ or self.segments_[-1][1] >= SEGMENT_BYTES:
            self.segments_.append([_seq_of(self.pending_[0]), 0])
        seg = self.segments_[-1]
        data = ''.join(self.pending_)
        with open(self._path(seg[0]), 'a') as f:
            f.write(data)
        seg[1] += len(data)
        self.pending_ = []
        self.pending_bytes_ = 0
        with open(NEXT_FILE, 'w') as f:
            f.write(str(self.next_seq_))

    # --- replay -------------------------------------------------------------

    def ack(self, seq):
        if seq <= self.acked_ or seq >= self.next_seq_:
            return
        self.acked_ = seq
        # A segment is fully acknowledged when the next one starts after the ack.
        while len(self.segments_) > 1 and self.segments_[1][0] <= seq + 1:
            self._delete(self.segments_.pop(0))
        if (len(self.segments_) == 1 and not self.pending_ and not self.replaying_
                and seq + 1 >= self.next_seq_):
            self._delete(self.segments_.pop(0))

    def step(self, now_ms, pi_listening, send):
        """Flush on schedule, and replay to the Pi while it's listening."""
        if self.pending_ and time.ticks_diff(now_ms, self.last_flush_ms_) >= FLUSH_MS:
            self.flush(now_ms)
        if not pi_listening:
            if self.replaying_:
                # Whatever was sent and not acknowledged gets sent again.
                self.last_sent_ = self.acked_
            self.replaying_ = False
            self.batch_ = []
            return
        if not self.replaying_:
            if not self._should_start_pass(now_ms):
                return
            self.flush(now_ms)
            self.replaying_ = True
            self.cursor_ = (self.segments_[0][0], 0)
        if time.ticks_diff(now_ms, self.next_send_ms_) < 0:
            return
        line = self._next_line()
        if line is None:
            self.replaying_ = False
            self.pass_end_ms_ = now_ms
            return
        send(line)
        self.last_sent_ = max(self.last_sent_, _seq_of(line))
        self.replayed += 1
        self.next_send_ms_ = time.ticks_add(now_ms, REPLAY_INTERVAL_MS)

    def _should_start_pass(self, now_ms):
        if not self.segments_ and not self.pending_:
            return False
        if self.next_seq_ - 1 > self.last_sent_:
            return True  # records the Pi hasn't been sent yet
        # Everything was sent; resend only if acknowledgements have stalled.
        return (self.acked_ < self.last_sent_
                and time.ticks_diff(now_ms, self.pass_end_ms_) >= RESEND_AFTER_MS)

    @property
    def backlog(self):
        """Records stored and not yet acknowledged."""
        if not self.segments_ and not self.pending_:
            return 0
        first = self.segments_[0][0] if self.segments_ else _seq_of(self.pending_[0])
        return self.next_seq_ - max(first, self.acked_ + 1)

    @property
    def stored_bytes(self):
        return sum(s[1] for s in self.segments_) + self.pending_bytes_

    # --- internals ----------------------------------------------------------

    def _next_line(self):
        while True:
            if not self.batch_:
                self._read_batch()
                if not self.batch_:
                    return None
            line = self.batch_.pop(0)
            if _seq_of(line) > self.acked_:
                return line

    def _read_batch(self):
        while self.cursor_ is not None:
            first, offset = self.cursor_
            try:
                with open(self._path(first)) as f:
                    f.seek(offset)
                    for _ in range(REPLAY_BATCH):
                        line = f.readline()
                        if not line:
                            break
                        offset += len(line)
                        self.batch_.append(line)
            except OSError:
                pass
            self.cursor_ = (first, offset)
            if self.batch_:
                return
            # This segment is exhausted; move to the next, if any.
            later = [s[0] for s in self.segments_ if s[0] > first]
            self.cursor_ = (later[0], 0) if later else None

    def _enforce_limit(self):
        kept = 0
        while len(self.segments_) > 1 and self._over_limit():
            oldest = self.segments_.pop(0)
            events = self._events_in(oldest)
            self.dropped += self.segments_[0][0] - oldest[0] - len(events)
            self._delete(oldest)
            for message in events:
                self._append(message)
            kept += len(events)
        if kept:
            self._write_pending()

    def _over_limit(self):
        if self.stored_bytes > MAX_BYTES:
            return True
        free = _fs_free()
        return free is not None and free < FS_RESERVE_BYTES

    def _events_in(self, seg):
        events = []
        try:
            with open(self._path(seg[0])) as f:
                for line in f:
                    if _is_event(line):
                        try:
                            message = json.loads(line)
                        except ValueError:
                            continue
                        message.pop("seq", None)
                        events.append(message)
        except OSError:
            pass
        return events

    def _delete(self, seg):
        try:
            os.remove(self._path(seg[0]))
        except OSError:
            pass

    @staticmethod
    def _path(first_seq):
        return '{}/{:010d}.jl'.format(LOG_DIR, first_seq)

    @staticmethod
    def _scan():
        segments = []
        for name in os.listdir(LOG_DIR):
            if name.endswith('.jl'):
                try:
                    segments.append([int(name[:-3]), os.stat(LOG_DIR + '/' + name)[6]])
                except (ValueError, OSError):
                    pass
        segments.sort()
        return segments

    def _load_next_seq(self):
        n = 0
        try:
            with open(NEXT_FILE) as f:
                n = int(f.read().strip() or 0)
        except (OSError, ValueError):
            pass
        if self.segments_:
            # Covers a 'next' file that is missing or older than the last flush.
            with open(self._path(self.segments_[-1][0])) as f:
                last = None
                for line in f:
                    last = line
            if last:
                n = max(n, _seq_of(last) + 1)
        return n
