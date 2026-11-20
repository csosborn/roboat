import re
import time

# VE.Direct HEX, alongside the text frames on the same port. Only reads
# (command 7, "get") are ever sent: writing a setting once restarted the MPPT
# and dropped the Pi.
#
# Battery temperature comes from the Smart Battery Sense, over Bluetooth. With
# the sensor gone the MPPT holds the last value for a while (a few minutes to
# under 25, measured 2026-11-20), then answers 0xFFFF.
TEMP_REGISTER = 0xEDEC        # 0.01 K
TEMP_POLL_MS = 60000
TEMP_MISSES = 3               # unanswered polls before the reading is dropped
HEX_NOT_AVAILABLE = 0xFFFF


def hex_frame(cmd, payload=b""):
    """A VE.Direct HEX message: all its bytes, the command nibble included,
    sum to 0x55."""
    check = (0x55 - cmd - sum(payload)) & 0xFF
    return ":%X%s%02X\n" % (cmd, "".join("%02X" % b for b in payload), check)


def hex_get(register):
    return hex_frame(7, bytes([register & 0xFF, register >> 8, 0]))


def parse_hex(line):
    """(command, bytes) for a valid HEX message, else None."""
    s = line.strip()
    if len(s) < 4 or s[0] != ":" or len(s) % 2 != 0:
        return None
    try:
        cmd = int(s[1], 16)
        data = bytes(int(s[k:k + 2], 16) for k in range(2, len(s), 2))
    except ValueError:
        return None
    if (cmd + sum(data)) & 0xFF != 0x55:
        return None
    return cmd, data[:-1]


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
        self.charge_state = None  # VE.Direct CS: 3 bulk, 4 absorption, 5 float
        self.yield_total_kwh = 0
        self.error = 0
        self.load_on = None  # unknown until a frame reports LOAD
        self.battery_temp_c = None  # from the Battery Sense, via HEX
        self.temp_polled_ms_ = None
        self.temp_misses_ = 0
        self.temp_answered_ = False


    def update(self):
        mppt_line = self.uart_.readline()
        if mppt_line:
            try:
                self.update_str(mppt_line.decode("ascii", "ignore"))
            except UnicodeError as e:
                pass


    def poll(self, now_ms):
        """Ask for the battery temperature once every TEMP_POLL_MS."""
        if self.temp_polled_ms_ is not None and \
                time.ticks_diff(now_ms, self.temp_polled_ms_) < TEMP_POLL_MS:
            return
        if self.temp_polled_ms_ is not None:
            self.temp_misses_ = 0 if self.temp_answered_ else self.temp_misses_ + 1
            if self.temp_misses_ >= TEMP_MISSES:
                self.battery_temp_c = None
        self.temp_polled_ms_ = now_ms
        self.temp_answered_ = False
        if self.uart_ is not None:
            self.uart_.write(hex_get(TEMP_REGISTER))

    def update_hex(self, line):
        msg = parse_hex(line)
        if msg is None:
            return
        cmd, data = msg
        # 7: the answer to a get; A: sent unasked when a value changes.
        if cmd not in (0x7, 0xA) or len(data) < 5:
            return
        register = data[0] | data[1] << 8
        if register != TEMP_REGISTER or data[2] != 0:
            return
        raw = data[3] | data[4] << 8
        self.temp_answered_ = True
        if raw == HEX_NOT_AVAILABLE:
            self.battery_temp_c = None
        else:
            self.battery_temp_c = raw / 100 - 273.15

    def update_str(self, mppt_str):
        if mppt_str.startswith(":"):
            self.update_hex(mppt_str)
            return
        match = re.search(r"^([\w\#]+)\s([\w\.\-]+)\s+?$", mppt_str)
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
            if key == "CS":
                self.charge_state = val
            if key == "H19":
                self.yield_total_kwh = int(val) / 100
            if key == "ERR":
                self.error = val
            if key == "LOAD":
                self.load_on = val == "ON"

            if key == 'HSDS':
                self.active = True
                self.epoch = self.epoch + 1
            

