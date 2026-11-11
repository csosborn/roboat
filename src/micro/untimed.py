"""Holds records made before the GPS has given the board the time.

The board has no clock of its own, so until the GPS's first fix its records
carry no utc_ms, and the telemetry log (and InfluxDB) can't file them. After a
cold start that's the first minute or more (2 min 14 s on 2026-11-10): the
boot event, the load output coming on, the LiPo starting to charge. Those are
exactly the minutes a dawn wake wants on record.

So they're held here in RAM, encoded and stamped with ticks_ms. Once the clock
knows the time, release() stamps each with UTC by counting back from now, for
the telemetry log to store as usual. RAM is limited, so past LIMIT_BYTES the
oldest non-event records go first.

Only records the Pi might not have had belong here. One sent while the Pi was
listening reached InfluxDB live, stamped with the Pi's arrival time; storing it
too would add a second point at a slightly different time.
"""
import json
import time

# About 8 snapshots of all sources while the Pi is away: 8 minutes.
LIMIT_BYTES = 12288


class Untimed:

    def __init__(self, limit_bytes=LIMIT_BYTES):
        self.limit_ = limit_bytes
        self.held_ = []        # [ticks_ms, encoded record, is_event], oldest first
        self.bytes_ = 0
        self.dropped = 0       # records lost for want of room

    @property
    def held(self):
        return len(self.held_)

    def hold(self, message, now_ms):
        line = json.dumps(message)
        self.held_.append((now_ms, line, "event" in message))
        self.bytes_ += len(line)
        while self.bytes_ > self.limit_ and self.held_:
            victim = 0
            for i, h in enumerate(self.held_):
                if not h[2]:
                    victim = i
                    break
            self.bytes_ -= len(self.held_.pop(victim)[1])
            self.dropped += 1

    def delivered(self, since_ms):
        """Forgets the records held since since_ms: the Pi was listening for them."""
        keep = [h for h in self.held_ if time.ticks_diff(h[0], since_ms) < 0]
        self.held_ = keep
        self.bytes_ = sum(len(h[1]) for h in keep)

    def release(self, utc_now_ms, now_ms):
        """The held records, oldest first, each given its utc_ms, and forgets them.

        utc_now_ms is the clock's UTC at now_ms; pass None while the time is unknown,
        which releases nothing.
        """
        if utc_now_ms is None or not self.held_:
            return []
        out = []
        for ticks, line, _ in self.held_:
            message = json.loads(line)
            message["utc_ms"] = utc_now_ms + time.ticks_diff(ticks, now_ms)
            out.append(message)
        self.held_ = []
        self.bytes_ = 0
        return out
