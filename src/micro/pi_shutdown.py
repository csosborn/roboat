import time

REQUEST_INTERVAL_MS = 5000
# The monitor stops early in the Pi's shutdown; the rest takes a few seconds.
HALT_MARGIN_MS = 30000
TIMEOUT_MS = 120000


class PiShutdown:
    """A clean shutdown of the Pi: ask it to power off, then wait until it has
    been silent long enough to have halted before its power is cut.

    If the Pi is still talking after TIMEOUT_MS, the shutdown is given up on
    and its power is cut anyway: protecting the battery comes first.
    """

    def __init__(self):
        self.active = False
        self.timed_out = False

    def start(self, now_ms, reason):
        self.active = True
        self.timed_out = False
        self.reason = reason
        self.started_ms_ = now_ms
        self.last_request_ms_ = None
        self.quiet_since_ms_ = None

    def step(self, now_ms, pi_listening, send_request):
        """Returns True once it's time to cut the Pi's power."""
        if not self.active:
            return False
        if (self.last_request_ms_ is None
                or time.ticks_diff(now_ms, self.last_request_ms_) >= REQUEST_INTERVAL_MS):
            send_request(self.reason)
            self.last_request_ms_ = now_ms
        if pi_listening:
            self.quiet_since_ms_ = None
        elif self.quiet_since_ms_ is None:
            self.quiet_since_ms_ = now_ms
        halted = (self.quiet_since_ms_ is not None
                  and time.ticks_diff(now_ms, self.quiet_since_ms_) >= HALT_MARGIN_MS)
        if halted or time.ticks_diff(now_ms, self.started_ms_) >= TIMEOUT_MS:
            self.active = False
            self.timed_out = not halted
            return True
        return False
