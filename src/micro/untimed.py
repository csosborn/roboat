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
too would add a second point at a slightly different time. The RP2040 can't
always tell: after a reset, the Pi's first heartbeat comes up to 2 s after the
boot event. So every record is held at least HOLD_MS, even once the time is
known, and delivered() forgets those the Pi's first heartbeat shows it heard.
"""
import json
import time

# About 8 snapshots of all sources while the Pi is away: 8 minutes.
LIMIT_BYTES = 12288
# The Pi's monitor heartbeats every 2 s, so a record made this long before the
# Pi was first heard reached it live.
HOLD_MS = 3000


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

    def delivered(self, now_ms):
        """The Pi has just been heard: forgets the records it was listening for."""
        self._keep(lambda ticks: time.ticks_diff(now_ms, ticks) > HOLD_MS)

    def release(self, utc_now_ms, now_ms):
        """The records held at least HOLD_MS, oldest first, each given its utc_ms.

        They're forgotten here. utc_now_ms is the clock's UTC at now_ms; pass None
        while the time is unknown, which releases nothing.
        """
        if utc_now_ms is None or not self.held_:
            return []
        out = []
        for ticks, line, _ in self.held_:
            if time.ticks_diff(now_ms, ticks) < HOLD_MS:
                break
            message = json.loads(line)
            message["utc_ms"] = utc_now_ms + time.ticks_diff(ticks, now_ms)
            out.append(message)
        if out:
            self._keep(lambda ticks: time.ticks_diff(now_ms, ticks) < HOLD_MS)
        return out

    def _keep(self, wanted):
        self.held_ = [h for h in self.held_ if wanted(h[0])]
        self.bytes_ = sum(len(h[1]) for h in self.held_)
