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


from fakes import FakePin

machine = types.ModuleType('machine')
machine.Pin = FakePin
sys.modules.setdefault('machine', machine)
