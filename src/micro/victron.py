import re

class VictronMPPT:

    def __init__(self, uart):
        self.uart_ = uart
        self.active = False
        self.fields_ = {}
        self.epoch = 0
        self.panel_volts = 0
        self.panel_watts = 0
        self.battery_volts = 0
        self.battery_amps = 0
        self.load_amps = 0
        self.tracker_mode = 0
        self.yield_total_kwh = 0
        self.error = 0


    def update(self):
        mppt_line = self.uart_.readline()
        if mppt_line:
            try:
                self.update_str(mppt_line.decode("ascii", "ignore"))
            except UnicodeError as e:
                pass


    def update_str(self, mppt_str):
        match = re.search("^([\w\#]+)\s([\w\.\-]+)\s+?$", mppt_str)
        if match:
            self.fields_[match.group(1)] = match.group(2)
            key = match.group(1)
            val = match.group(2)
            if key == "VPV":
                self.panel_volts = int(val) / 1000
            if key == "PPV":
                self.panel_watts = int(val)
            if key == "V":
                self.battery_volts = int(val) / 1000
            if key == "I":
                self.battery_amps = int(val) / 1000
            if key == "IL":
                self.load_amps = int(val) / 1000
            if key == "MPPT":
                self.tracker_mode = val
            if key == "H19":
                self.yield_total_kwh = int(val) / 100
            if key == "ERR":
                self.error = val

            if key == 'HSDS':
                self.active = True
                self.epoch = self.epoch + 1
            