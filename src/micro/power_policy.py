"""What the Pi's power (GPIO11, high = on) should do as the RP2040 comes out of reset.

- Cold start (power-on reset, which includes the reset button): the whole
  system may just be waking on a nearly empty battery, so the Pi stays off
  until the FSM's energy rules start it.
- Watchdog reset (a crash, a hang, or a deploy's machine.reset()): the system
  was running, so restore whatever the firmware last chose deliberately.
- Soft reset (Ctrl-D): the pin is still being driven; leave it alone.
"""

PI_POWER_FILE = 'pi_power'


def pi_power_at_boot(cold_start, pin_driven, last_choice):
    """Returns 0 or 1 to drive the pin, or None to leave it untouched."""
    if pin_driven:
        return None
    if cold_start:
        return 0
    return 1 if last_choice is None else last_choice


def read_last_choice():
    try:
        with open(PI_POWER_FILE) as f:
            value = f.read(1)
    except OSError:
        return None
    return {'0': 0, '1': 1}.get(value)


class ChoiceRecorder:
    """Persists deliberate Pi power changes, writing flash only when they change."""

    def __init__(self):
        self.last_ = read_last_choice()

    def __call__(self, on):
        value = 1 if on else 0
        if value == self.last_:
            return
        try:
            with open(PI_POWER_FILE, 'w') as f:
                f.write(str(value))
            self.last_ = value
        except OSError:
            pass
