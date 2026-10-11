class SharedBus:
    """An I2C bus shared by several drivers, any of which may need it rebuilt.

    Drivers call get() on every use rather than keeping the bus object, so a
    rebuild after errors reaches all of them.
    """

    def __init__(self, make_bus):
        self.make_bus_ = make_bus
        self.bus_ = None
        self.rebuilds = 0

    def get(self):
        if self.bus_ is None:
            self.bus_ = self.make_bus_()
        return self.bus_

    def rebuild(self):
        self.bus_ = None
        self.rebuilds += 1
