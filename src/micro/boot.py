# Runs before main.py on every reset, so the Pi's power relay is settled
# before anything that could fail. See power_policy.py for the rules.
import machine
from machine import Pin, mem32

PI_POWER_PIN = 11

# IO_BANK0 GPIO11_CTRL. Any hard reset sets FUNCSEL to 0x1f (no function);
# it reads 5 (SIO) only if main.py is still driving the pin, i.e. after a
# soft reset.
GPIO_CTRL = 0x40014000 + 8 * PI_POWER_PIN + 4
FUNCSEL_SIO = 5

try:
    import power_policy
    level = power_policy.pi_power_at_boot(
        cold_start=machine.reset_cause() == machine.PWRON_RESET,
        pin_driven=(mem32[GPIO_CTRL] & 0x1f) == FUNCSEL_SIO,
        last_choice=power_policy.read_last_choice())
    if level is not None:
        Pin(PI_POWER_PIN, Pin.OUT, value=level)
except Exception:
    # Leave the relay to the hardware pull-up (on); main.py takes over.
    pass
