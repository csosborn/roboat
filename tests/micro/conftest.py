"""Lets the RP2040 firmware's pure-Python parts run under CPython.

Provides stand-ins for MicroPython's hardware modules and its time extensions.
The firmware's lib/ is appended to sys.path (not prepended) so its vendored
'collections' doesn't shadow the standard library's.
"""
import os
import sys
import time
import types

MICRO_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'micro')
sys.path.insert(0, os.path.abspath(MICRO_DIR))
sys.path.append(os.path.abspath(os.path.join(MICRO_DIR, 'lib')))

time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b
time.sleep_ms = lambda ms: None


class FakePin:
    OUT = 1
    IN = 0

    def __init__(self, value=0):
        self._value = value

    def value(self, v=None):
        if v is None:
            return self._value
        self._value = 1 if v else 0

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0


class FakePWM:
    def __init__(self):
        self._duty = 0

    def duty_ns(self, v=None):
        if v is None:
            return self._duty
        self._duty = v


class FakeNeoPixel(list):
    def __init__(self):
        super().__init__([(0, 0, 0)])

    def write(self):
        pass


machine = types.ModuleType('machine')
machine.Pin = FakePin
sys.modules.setdefault('machine', machine)
