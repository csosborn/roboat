"""Writes points to InfluxDB without losing them to a brief outage.

Failed points wait in a bounded queue and are retried before newer ones, so
InfluxDB starting after the monitor (as at boot) or restarting doesn't crash
the monitor or drop data. If the outage outlasts the queue, the oldest points
are dropped.
"""
from collections import deque

MAX_QUEUED = 20000


class QueuedWriter:
    def __init__(self, write, max_queued=MAX_QUEUED):
        self.write_ = write
        self.queue_ = deque(maxlen=max_queued)  # (point, seq or None)
        self.failures = 0
        # Highest RP2040 sequence number written. Points are written in
        # order, so everything up to it has been written too.
        self.acked_seq = None

    def write(self, point, seq=None):
        self.queue_.append((point, seq))
        self.flush()

    def flush(self):
        while self.queue_:
            point, seq = self.queue_[0]
            try:
                self.write_(point)
            except Exception as err:
                self.failures += 1
                if self.failures == 1 or self.failures % 100 == 0:
                    print("InfluxDB write failed ({} queued): {!r}".format(len(self.queue_), err))
                return False
            self.queue_.popleft()
            if seq is not None and (self.acked_seq is None or seq > self.acked_seq):
                self.acked_seq = seq
        if self.failures:
            print("InfluxDB writes resumed after {} failures".format(self.failures))
            self.failures = 0
        return True
