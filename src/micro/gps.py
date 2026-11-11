import time

import nmea
from clock import utc_ms

GPS_ADDR = 0x10  # Adafruit Mini GPS PA1010D
POLL_MS = 50
READ_BYTES = 64
ERROR_BACKOFF_MS = 1000
# An RMC sets the clock only if it was read this close to the time since the
# last RMC that its own time says has passed (see GpsMonitor).
RMC_MATCH_MS = 200
MAX_LINE = 100

# Output only RMC, GGA, and GSA, once per fix.
OUTPUT_CONFIG = nmea.pmtk('PMTK314,0,1,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
# Sentences the configuration turns off; seeing one means the module has lost
# its configuration (e.g. after losing power) and needs it again.
UNWANTED = ('GSV', 'VTG', 'GLL')


class GpsMonitor:
    """Reads NMEA from the PA1010D over I2C, reports fixes, and sets the clock.

    Over I2C the module returns '\\n' bytes as padding when it has nothing to
    send; real sentences end with '\\r\\n'.

    The module keeps sending while nobody reads, and buffers what it sends: after
    the RP2040 resets, the first sentences read can be seconds old (12 s after a
    deploy on 2026-11-10). Padding doesn't show the backlog is gone: the module
    pads between fixes while it still has one. But a backlog reads faster than
    real time (an RMC every 0.2 s against one a second), so an RMC is current only
    if the time since the last one, by ticks, matches the step in their GPS times.
    Only then does it set the clock. This also skips the stale RMC read after the
    RP2040 has been too busy to read for a second or more.
    """

    def __init__(self, bus, pi_link, clock, now_ms):
        self.bus_ = bus
        self.pi_link_ = pi_link
        self.clock_ = clock
        self.buf_ = bytearray()
        self.next_poll_ms_ = now_ms
        self.configured_ = False
        self.fix_type_ = 0
        self.last_rmc_ = None  # (utc_ms, ticks) of the last RMC with a time
        self.gga_ = {}
        self.errors = 0
        self.fixes = 0

    @property
    def mode(self):
        return self.fix_type_

    def step(self, now_ms):
        if time.ticks_diff(now_ms, self.next_poll_ms_) < 0:
            return
        try:
            i2c = self.bus_.get()
            if not self.configured_:
                i2c.writeto(GPS_ADDR, OUTPUT_CONFIG)
                self.configured_ = True
            data = i2c.readfrom(GPS_ADDR, READ_BYTES)
        except OSError:
            self.errors += 1
            self.next_poll_ms_ = time.ticks_add(now_ms, ERROR_BACKOFF_MS)
            return
        self.next_poll_ms_ = time.ticks_add(now_ms, POLL_MS)
        self._feed(data, now_ms)

    def _feed(self, data, now_ms):
        for b in data:
            if b == 0x0A:
                if self.buf_ and self.buf_[-1] == 0x0D:
                    line = bytes(self.buf_[:-1])
                    self.buf_ = bytearray()
                    self._handle(line, now_ms)
                # Otherwise it's padding.
            else:
                self.buf_.append(b)
                if len(self.buf_) > MAX_LINE:
                    self.buf_ = bytearray()

    def _handle(self, line, now_ms):
        try:
            parsed = nmea.split(line.decode())
            if parsed is None:
                return
            kind, fields = parsed
            if kind in UNWANTED:
                self.configured_ = False
            elif kind == 'GSA':
                self.fix_type_ = nmea.parse_gsa(fields)['fix_type']
            elif kind == 'GGA':
                self.gga_ = nmea.parse_gga(fields)
            elif kind == 'RMC':
                self._report(nmea.parse_rmc(fields), now_ms)
        except (ValueError, IndexError, UnicodeError):
            self.errors += 1

    def _report(self, rmc, now_ms):
        if rmc['valid'] and 'date' in rmc and 'time' in rmc:
            utc = utc_ms(rmc['date'], rmc['time'])
            last = self.last_rmc_
            if last is not None and abs(
                    time.ticks_diff(now_ms, last[1]) - (utc - last[0])) <= RMC_MATCH_MS:
                self.clock_.set(utc, now_ms)
            self.last_rmc_ = (utc, now_ms)
        fields = {"error": 0, "mode": self.fix_type_ if rmc['valid'] else 1,
                  "sats": self.gga_.get('sats', 0)}
        if rmc['valid'] and rmc['lat_e7'] is not None and rmc['lon_e7'] is not None:
            self.fixes += 1
            fields["lat_e7"] = rmc['lat_e7']
            fields["lon_e7"] = rmc['lon_e7']
            if rmc['speed_mps'] is not None:
                fields["hspeed"] = rmc['speed_mps']
            if rmc['track_deg'] is not None:
                fields["track"] = rmc['track_deg']
            if 'date' in rmc and 'time' in rmc:
                y, mo, d = rmc['date']
                h, mi, s, ms = rmc['time']
                fields["time"] = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.{:03d}Z".format(
                    y, mo, d, h, mi, s, ms)
            if self.fix_type_ >= 3 and self.gga_.get('alt_m') is not None:
                fields["alt"] = self.gga_['alt_m']
        self.pi_link_.send_update("gps", fields)
