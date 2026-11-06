import pytest

from fakes import FakePin
import power_sense as ps


class FakeADC:
    def __init__(self, values):
        self.values = list(values)

    def read_u16(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


def test_lipo_reading_undoes_the_divider_and_averages():
    # 2.1 V at the pin is a full 4.2 V LiPo.
    code = round(2.1 / 3.3 * 65535)
    sense = ps.LipoSense(FakeADC([code - 8, code + 8] * 8))
    assert sense.volts() == pytest.approx(4.2, abs=0.002)


def run(check, pg, now):
    events = []
    check.step(now, events.append)
    return events


def test_supply_fault_reported_once_after_the_grace_period():
    power, pg = FakePin(0), FakePin(0)
    check = ps.PiSupplyCheck(pg, power, now_ms=0)
    assert run(check, pg, 1000) == []          # Pi off: power-good low is expected
    power.value(1)
    assert run(check, pg, 2000) == []
    assert run(check, pg, 2000 + ps.PI_SUPPLY_GRACE_MS - 1) == []
    assert run(check, pg, 2000 + ps.PI_SUPPLY_GRACE_MS) == ["pi_supply_fault"]
    assert run(check, pg, 9000) == []
    pg.value(1)
    assert run(check, pg, 9500) == ["pi_supply_good"]


def test_healthy_supply_reports_nothing():
    power, pg = FakePin(1), FakePin(1)
    check = ps.PiSupplyCheck(pg, power, now_ms=0)
    assert run(check, pg, 10000) == [] and check.good


def test_turning_the_pi_off_clears_a_fault():
    power, pg = FakePin(1), FakePin(0)
    check = ps.PiSupplyCheck(pg, power, now_ms=0)
    assert run(check, pg, ps.PI_SUPPLY_GRACE_MS) == ["pi_supply_fault"]
    power.value(0)
    run(check, pg, 5000)
    power.value(1)
    assert run(check, pg, 5001) == []
    assert run(check, pg, 5001 + ps.PI_SUPPLY_GRACE_MS) == ["pi_supply_fault"]
