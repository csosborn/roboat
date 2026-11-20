import pytest

import victron
from victron import VictronMPPT

FRAME = [
    "PID\t0xA053", "FW\t159", "V\t13160", "I\t3440", "VPV\t19860", "PPV\t54",
    "CS\t3", "MPPT\t1", "ERR\t0", "LOAD\tON", "IL\t500", "H19\t2599", "HSDS\t42",
]


def feed(mppt, lines):
    for line in lines:
        mppt.update_str(line + "\r\n")


def test_parses_a_frame():
    m = VictronMPPT(uart=None)
    feed(m, FRAME)
    assert m.active and m.epoch == 1
    assert m.battery_volts == pytest.approx(13.16)
    assert m.battery_amps == pytest.approx(3.44)
    assert m.panel_volts == pytest.approx(19.86)
    assert m.panel_watts == 54
    assert m.load_amps == pytest.approx(0.5)
    assert m.yield_total_kwh == pytest.approx(25.99)
    assert m.load_on is True


def test_frame_joined_part_way_through_lacks_voltage():
    m = VictronMPPT(uart=None)
    feed(m, FRAME[FRAME.index("PPV\t54"):])
    assert m.active and m.epoch == 1
    assert m.battery_volts == 0


def test_garbled_numeric_field_raises_value_error():
    m = VictronMPPT(uart=None)
    with pytest.raises(ValueError):
        m.update_str("V\t13x60\r\n")


class FakeUart:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)


def answer(cmd, register, value, flags=0):
    return victron.hex_frame(cmd, bytes([register & 0xFF, register >> 8, flags,
                                         value & 0xFF, value >> 8]))


def test_hex_frames_match_the_mppt():
    # As sent to, and answered by, the boat's MPPT on 2026-11-20.
    assert victron.hex_frame(1) == ":154\n"
    assert victron.hex_get(0xEDEC) == ":7ECED0075\n"
    assert victron.parse_hex(":575419A\n") == (5, bytes([0x75, 0x41]))
    assert victron.parse_hex(":575419B\n") is None    # bad checksum
    assert victron.parse_hex("V\t13050\r\n") is None


def test_battery_temperature_from_a_get_answer_and_an_async_update():
    m = VictronMPPT(uart=None)
    m.update_str(answer(7, 0xEDEC, 28950) + "\r")  # 289.50 K
    assert m.battery_temp_c == pytest.approx(16.35)
    m.update_str(":AECED000C71F5\n")              # 289.40 K, sent unasked (recorded)
    assert m.battery_temp_c == pytest.approx(16.25)


def test_temperature_not_available_once_the_sensor_is_gone():
    m = VictronMPPT(uart=None)
    m.update_str(":AECED000C71F5\n")
    m.update_str(":AECED00FFFF74\n")              # recorded with the sensor unplugged
    assert m.battery_temp_c is None


def test_other_registers_and_unknown_ids_are_ignored():
    m = VictronMPPT(uart=None)
    m.update_str(answer(7, 0xEDD5, 1324))          # charger voltage
    m.update_str(answer(7, 0xEDEC, 28940, flags=1))  # flags 01: unknown id
    assert m.battery_temp_c is None
    assert m.battery_volts == 0


def test_polls_once_a_minute_and_drops_a_reading_nobody_confirms():
    uart = FakeUart()
    m = VictronMPPT(uart=uart)
    m.poll(0)
    m.poll(30000)
    assert uart.written == [":7ECED0075\n"]
    m.update_str(answer(7, 0xEDEC, 28940))
    t = victron.TEMP_POLL_MS
    m.poll(t)                                      # closes the answered window
    for _ in range(victron.TEMP_MISSES):
        assert m.battery_temp_c is not None
        t += victron.TEMP_POLL_MS
        m.poll(t)
    assert m.battery_temp_c is None
    assert len(uart.written) == 2 + victron.TEMP_MISSES
