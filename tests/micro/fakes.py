"""Stand-ins for MicroPython hardware objects used by the tests."""


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
