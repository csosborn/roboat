"""Minimal NMEA 0183 parsing for the sentences the GPS is configured to send.

Coordinates are returned as integer 1e-7 degrees and times as integer
milliseconds, because MicroPython floats on the RP2040 are 32-bit.
"""


def checksum(body):
    c = 0
    for ch in body:
        c ^= ord(ch)
    return c


def pmtk(body):
    """Frame a MediaTek PMTK command, e.g. pmtk('PMTK314,...')."""
    return '${}*{:02X}\r\n'.format(body, checksum(body)).encode()


def split(line):
    """Return (sentence type, fields) for a valid sentence, or None.

    The type drops the talker ID, so '$GNRMC,...' gives ('RMC', [...]).
    """
    line = line.strip()
    if len(line) < 9 or line[0] != '$' or line[-3] != '*':
        return None
    body = line[1:-3]
    try:
        if checksum(body) != int(line[-2:], 16):
            return None
    except ValueError:
        return None
    fields = body.split(',')
    return fields[0][2:], fields[1:]


def coord_e7(value, hemisphere):
    """'3746.4940', 'N' -> 377749000. Returns None if empty."""
    if not value or not hemisphere:
        return None
    dot = value.find('.')
    if dot < 0:
        dot = len(value)
    degrees = int(value[:dot - 2])
    whole_minutes = value[dot - 2:dot]
    frac = value[dot + 1:]
    scale = 10 ** len(frac)
    minutes_scaled = int(whole_minutes) * scale + (int(frac) if frac else 0)
    e7 = degrees * 10000000 + minutes_scaled * 10000000 // (60 * scale)
    return -e7 if hemisphere in 'SW' else e7


def _float(value):
    return float(value) if value else None


def _int(value):
    return int(value) if value else None


def parse_time(hhmmss):
    """'123519.250' -> (12, 35, 19, 250)."""
    ms = 0
    if '.' in hhmmss:
        hhmmss, frac = hhmmss.split('.')
        ms = int((frac + '000')[:3])
    return int(hhmmss[0:2]), int(hhmmss[2:4]), int(hhmmss[4:6]), ms


def parse_rmc(f):
    rmc = {'valid': f[1] == 'A'}
    if f[0]:
        rmc['time'] = parse_time(f[0])
    if f[8] and len(f[8]) == 6:
        rmc['date'] = (2000 + int(f[8][4:6]), int(f[8][2:4]), int(f[8][0:2]))
    rmc['lat_e7'] = coord_e7(f[2], f[3])
    rmc['lon_e7'] = coord_e7(f[4], f[5])
    knots = _float(f[6])
    rmc['speed_mps'] = knots * 0.514444 if knots is not None else None
    rmc['track_deg'] = _float(f[7])
    return rmc


def parse_gga(f):
    return {'quality': _int(f[5]) or 0, 'sats': _int(f[6]) or 0, 'alt_m': _float(f[8])}


def parse_gsa(f):
    return {'fix_type': _int(f[1]) or 1}
