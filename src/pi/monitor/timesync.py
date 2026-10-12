"""Feeds the RP2040's GPS time to chrony as a reference clock.

chrony's SOCK refclock reads samples from a Unix datagram socket that chronyd
itself creates (see src/pi/etc/chrony/conf.d/roboat.conf). Each sample says
how far the system clock was from true time at a given moment. Without a PPS
signal the samples are good to roughly 0.1 s, so chrony is configured to
prefer internet time whenever it's reachable.
"""
import socket
import struct

SOCK_MAGIC = 0x534F434B


def encode_sample(system_time, offset):
    """chrony's struct sock_sample: timeval, offset, pulse, leap, padding, magic."""
    sec = int(system_time)
    usec = int(round((system_time - sec) * 1e6))
    if usec >= 1000000:
        sec, usec = sec + 1, usec - 1000000
    return struct.pack("@qqdiiii", sec, usec, offset, 0, 0, 0, SOCK_MAGIC)


class ChronyRefclock:
    def __init__(self, path):
        self.path = path
        self.sock_ = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sent = 0
        self.errors = 0

    def send(self, system_time, true_time):
        try:
            self.sock_.sendto(encode_sample(system_time, true_time - system_time), self.path)
            self.sent += 1
        except OSError as err:
            self.errors += 1
            if self.errors == 1 or self.errors % 1000 == 0:
                print("chrony refclock unavailable at {} ({} errors): {!r}".format(
                    self.path, self.errors, err))
