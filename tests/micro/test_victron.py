import pytest

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
