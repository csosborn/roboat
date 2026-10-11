import datetime
import json
import time

import pytest

import clock as clk
import gps as gps_mod
import nmea
from pi_link import PiLink
from shared_bus import SharedBus


def sentence(body):
    return '${}*{:02X}\r\n'.format(body, nmea.checksum(body)).encode()


RMC = sentence('GNRMC,190438.250,A,3746.4940,N,12225.1640,W,1.94,87.5,111026,,,A')
RMC_NO_FIX = sentence('GNRMC,190438.000,V,,,,,,,111026,,,N')
GGA = sentence('GNGGA,190438.250,3746.4940,N,12225.1640,W,1,08,0.9,12.3,M,-25.0,M,,')
GSA = sentence('GPGSA,A,3,04,05,09,12,,,,,,,,,1.8,0.9,1.5')
GSV = sentence('GPGSV,3,1,11,04,40,083,46,05,13,224,37,09,51,251,47,12,23,309,42')


# --- NMEA ---------------------------------------------------------------------

def test_pmtk_framing_matches_adafruit_constants():
    assert nmea.pmtk('PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0').endswith(b'*28\r\n')


def test_bad_checksum_rejected():
    assert nmea.split(RMC.decode().replace('1.94', '1.95')) is None
    assert nmea.split('garbage') is None


def test_coordinates_are_exact_integers():
    assert nmea.coord_e7('3746.4940', 'N') == 377749000
    assert nmea.coord_e7('12225.1640', 'W') == -1224194000
    assert nmea.coord_e7('', 'N') is None


def test_rmc_parsed():
    kind, fields = nmea.split(RMC.decode())
    rmc = nmea.parse_rmc(fields)
    assert kind == 'RMC' and rmc['valid']
    assert rmc['date'] == (2026, 10, 11) and rmc['time'] == (19, 4, 38, 250)
    assert rmc['speed_mps'] == pytest.approx(1.94 * 0.514444)
    assert rmc['track_deg'] == 87.5


# --- Clock --------------------------------------------------------------------

@pytest.mark.parametrize("dt", [
    datetime.datetime(1970, 1, 1), datetime.datetime(2000, 2, 29, 23, 59, 59),
    datetime.datetime(2026, 10, 11, 19, 4, 38, 250000), datetime.datetime(2099, 12, 31)])
def test_utc_ms_matches_python(dt):
    expected = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    got = clk.utc_ms((dt.year, dt.month, dt.day),
                     (dt.hour, dt.minute, dt.second, dt.microsecond // 1000))
    assert got == expected


def test_clock_runs_from_ticks_and_expires():
    c = clk.Clock()
    assert c.now_ms(0) is None
    c.set(1000000, at_ticks=500)
    assert c.now_ms(1500) == 1001000
    assert c.now_ms(500 + clk.MAX_AGE_MS + 1) is None


# --- GpsMonitor ---------------------------------------------------------------

class FakeI2C:
    def __init__(self, stream=b'', fail=False):
        self.stream = stream
        self.fail = fail
        self.writes = []

    def writeto(self, addr, data):
        if self.fail:
            raise OSError(5)
        self.writes.append(data)

    def readfrom(self, addr, n):
        if self.fail:
            raise OSError(5)
        chunk, self.stream = self.stream[:n], self.stream[n:]
        return chunk + b'\n' * (n - len(chunk))  # the PA1010D pads with LF


class FakeLink:
    def __init__(self):
        self.sent = []

    def send_update(self, src, data):
        self.sent.append((src, data))


def make(stream=b'', fail=False):
    i2c = FakeI2C(stream, fail)
    link = FakeLink()
    c = clk.Clock()
    mon = gps_mod.GpsMonitor(SharedBus(lambda: i2c), link, c, now_ms=0)
    return mon, i2c, link, c


def drain(mon, start=0, polls=20):
    t = start
    for _ in range(polls):
        mon.step(t)
        t += gps_mod.POLL_MS
    return t


def test_fix_reported_and_clock_set():
    mon, i2c, link, c = make(GSA + GGA + RMC)
    drain(mon)
    assert i2c.writes == [gps_mod.OUTPUT_CONFIG]
    [(src, fix)] = link.sent
    assert src == 'gps'
    assert fix['mode'] == 3 and fix['sats'] == 8
    assert fix['lat_e7'] == 377749000 and fix['lon_e7'] == -1224194000
    assert fix['alt'] == 12.3
    assert fix['time'] == '2026-10-11T19:04:38.250Z'
    assert c.now_ms() is not None


def test_no_fix_reports_mode_without_position_or_time():
    mon, i2c, link, c = make(RMC_NO_FIX)
    drain(mon)
    [(_, fix)] = link.sent
    assert fix['mode'] == 1 and 'lat_e7' not in fix
    assert c.now_ms() is None


def test_sentence_split_across_reads_and_padding():
    mon, i2c, link, c = make(b'\n\n' + GSA + GGA[:10] + b'\n' + GGA[10:] + RMC)
    drain(mon)
    assert len(link.sent) == 1


def test_lost_configuration_is_resent():
    mon, i2c, link, c = make(GSV + RMC)
    drain(mon)
    assert i2c.writes == [gps_mod.OUTPUT_CONFIG, gps_mod.OUTPUT_CONFIG]


def test_missing_gps_backs_off_instead_of_hammering_the_bus():
    mon, i2c, link, c = make(fail=True)
    drain(mon, polls=20)  # one second of polling time
    assert mon.errors == 1


def test_messages_carry_utc_once_time_is_known():
    class Uart:
        def __init__(self):
            self.out = b''

        def write(self, s):
            self.out += s.encode() if isinstance(s, str) else s

    c = clk.Clock()
    uart = Uart()
    link = PiLink(uart, c)
    link.send_update("ina260", {"batt_v": 13.2})
    assert b'utc_ms' not in uart.out
    c.set(1791752678250, at_ticks=time.ticks_ms())
    link.send_update("ina260", {"batt_v": 13.2})
    msg = json.loads(uart.out.splitlines()[-1])
    assert 1791752678250 <= msg["utc_ms"] < 1791752678250 + 1000
