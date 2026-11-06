"""Direct readings of the supplies: the Feather's LiPo, and the Pi's 5 V.

The LiPo (BAT pin) reaches A0 (GPIO26) through a 100k/100k divider with a
0.1 uF capacitor at the pin. The ADC's reference is the Feather's own 3.3 V
rail, which sags once the LiPo falls below about 3.4 V, so readings below that
are only approximate.

The Pi supply's power-good output (PG, open drain) reaches GPIO10 through a
divider powered by that supply's own output (10k from 5 V, 15k to ground), so
the pin is high only while the supply is enabled and its output is in range.
It reads low whenever the Pi is deliberately off.
"""
import time

LIPO_PIN = 26
LIPO_DIVIDER = 2.0
# Measured BAT voltage / reported voltage, from a one-point calibration
# against a multimeter.
LIPO_CAL = 1.0
LIPO_SAMPLES = 16
ADC_REF_V = 3.3

PI_SUPPLY_GOOD_PIN = 10
# The supply soft-starts in milliseconds; allow for that before calling a
# missing power-good a fault.
PI_SUPPLY_GRACE_MS = 3000


class LipoSense:

    def __init__(self, adc):
        self.adc_ = adc

    def volts(self):
        total = 0
        for _ in range(LIPO_SAMPLES):
            total += self.adc_.read_u16()
        return round(total / LIPO_SAMPLES * ADC_REF_V / 65535 * LIPO_DIVIDER * LIPO_CAL, 3)


class PiSupplyCheck:
    """Reports when the Pi's supply should be on but its power-good is low."""

    def __init__(self, pg_pin, pi_power_pin, now_ms):
        self.pg_ = pg_pin
        self.power_ = pi_power_pin
        self.on_since_ = now_ms if pi_power_pin.value() else None
        self.faulted_ = False

    @property
    def good(self):
        return self.pg_.value() == 1

    def step(self, now_ms, notify):
        if not self.power_.value():
            self.on_since_ = None
            self.faulted_ = False
            return
        if self.on_since_ is None:
            self.on_since_ = now_ms
        if self.good:
            if self.faulted_:
                self.faulted_ = False
                notify("pi_supply_good")
        elif not self.faulted_ and time.ticks_diff(now_ms, self.on_since_) >= PI_SUPPLY_GRACE_MS:
            self.faulted_ = True
            notify("pi_supply_fault")
