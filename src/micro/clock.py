"""UTC time for this board, disciplined by the GPS.

Kept as integer milliseconds since the Unix epoch (MicroPython floats are
32-bit, too coarse for timestamps), anchored to time.ticks_ms() at the last
GPS fix.
"""
import time

DAY_MS = 86400000
# ticks_diff is only meaningful for intervals under about six days.
MAX_AGE_MS = 3 * DAY_MS


def days_from_civil(y, m, d):
    """Days since 1970-01-01 for a proleptic Gregorian date."""
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def utc_ms(date, hms):
    y, mo, d = date
    h, mi, s, ms = hms
    return (((days_from_civil(y, mo, d) * 24 + h) * 60 + mi) * 60 + s) * 1000 + ms


class Clock:
    def __init__(self):
        self.base_utc_ms_ = None
        self.base_ticks_ = None

    def set(self, utc, at_ticks):
        self.base_utc_ms_ = utc
        self.base_ticks_ = at_ticks

    def now_ms(self, at_ticks=None):
        """UTC milliseconds, or None if the GPS hasn't provided time recently."""
        if self.base_utc_ms_ is None:
            return None
        if at_ticks is None:
            at_ticks = time.ticks_ms()
        age = time.ticks_diff(at_ticks, self.base_ticks_)
        if age < 0 or age > MAX_AGE_MS:
            return None
        return self.base_utc_ms_ + age

    @property
    def valid(self):
        return self.now_ms() is not None
