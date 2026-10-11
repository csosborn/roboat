"""Keeps the RP2040 recoverable when its main program fails.

- The watchdog is fed from a timer, but only while the main loop keeps checking
  in or a maintenance window is open, so a crash or hang ends in a reset
  instead of a silently stopped program.
- Every boot is counted, and the count is cleared once the main loop has run
  for HEALTHY_AFTER_MS. Too many boots in a row without getting that far means
  a crash loop, and the next boot comes up in safe mode instead.
- Uncaught exceptions are appended to a crash log on flash.
"""
import os
import sys
import time

BOOTCOUNT_FILE = 'bootcount'
CRASH_LOG = 'crash.log'
CRASH_LOG_OLD = 'crash.log.1'
NOWDT_FLAG = 'nowdt'

SAFE_MODE_AFTER_BOOTS = 3
HEALTHY_AFTER_MS = 60000
WDT_TIMEOUT_MS = 8000  # the RP2040 maximum is 8388
LIVENESS_MS = 5000
MAINTENANCE_S = 900
CRASH_LOG_MAX_BYTES = 4096


def _size(path):
    try:
        return os.stat(path)[6]
    except OSError:
        return -1


def wdt_disabled():
    """True when a 'nowdt' file exists, for interactive bench work."""
    return _size(NOWDT_FLAG) >= 0


def read_bootcount():
    try:
        with open(BOOTCOUNT_FILE) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def _write_bootcount(n):
    with open(BOOTCOUNT_FILE, 'w') as f:
        f.write(str(n))


def record_boot():
    """Count this boot. Returns (boot_number, enter_safe_mode)."""
    n = read_bootcount() + 1
    try:
        _write_bootcount(n)
    except OSError:
        pass
    return n, n > SAFE_MODE_AFTER_BOOTS


def mark_healthy():
    try:
        _write_bootcount(0)
    except OSError:
        pass


def record_crash(exc, uptime_ms):
    try:
        if _size(CRASH_LOG) > CRASH_LOG_MAX_BYTES:
            try:
                os.remove(CRASH_LOG_OLD)
            except OSError:
                pass
            os.rename(CRASH_LOG, CRASH_LOG_OLD)
        with open(CRASH_LOG, 'a') as f:
            f.write('--- crash at uptime {} ms\n'.format(uptime_ms))
            print_exception = getattr(sys, 'print_exception', None)
            if print_exception is not None:
                print_exception(exc, f)
            else:
                import traceback
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
    except OSError:
        pass


class Liveness:
    """Decides whether the watchdog may be fed."""

    def __init__(self, now_ms):
        self.last_alive = now_ms
        self.maintenance_until = None

    def alive(self, now_ms):
        self.last_alive = now_ms

    def start_maintenance(self, now_ms, seconds=MAINTENANCE_S):
        self.maintenance_until = time.ticks_add(now_ms, seconds * 1000)

    def in_maintenance(self, now_ms):
        return (self.maintenance_until is not None
                and time.ticks_diff(self.maintenance_until, now_ms) > 0)

    def should_feed(self, now_ms):
        if self.in_maintenance(now_ms):
            return True
        return time.ticks_diff(now_ms, self.last_alive) < LIVENESS_MS

