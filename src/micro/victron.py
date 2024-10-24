import re

class VictronMPPT:

    def __init__(self):
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

    def update(self, mppt_str):
        match = re.search("^([\w\#]+)\s([\w\.\-]+)\s+?$", mppt_str)
        if match:
            self.fields_[match.group(1)] = match.group(2)
            # print("{}={}".format(match.group(1), match.group(2)))
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

        # {
        #     'PID': '0xA074', 
        #     'SER#': 'HQ2245QWPH7', 
        #     # 'MPPT': '0', 
        #     # 'PPV': '0', 
        #     'OR': '0x00000001', 
        #     # 'VPV': '10', 
        #     'H19': '133', 
        #     'LOAD': 'ON', 
        #     # 'I': '-370', 
        #     # 'IL': '300', 
        #     'H22': '15', 
        #     # 'V': '13010', 
        #     'H20': '0', 
        #     'CS': '0', 
        #     'H21': '0', 
        #     'H23': '87', 
        #     'HSDS': '81', 
        #     'FW': '164', 
        #     # 'ERR': '0'
        # }
            

