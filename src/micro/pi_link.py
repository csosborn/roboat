import json

MAX_COMMAND = 256


class PiLink:
    """The serial link to the Pi: JSON telemetry out, JSON commands in.

    Each message is one line. While the Pi is off, its transmit line idles
    low and this side may see noise, so anything that isn't a complete,
    printable JSON object with a "cmd" field is ignored.
    """

    def __init__(self, uart, clock=None):
        self.uart_ = uart
        self.clock_ = clock
        self.rx_ = bytearray()
        self.rx_bad_ = False

    def send_update(self, src, data):
        update_msg = {
            "offset_s": 0,
            "src": src
        }
        if self.clock_ is not None:
            utc_ms = self.clock_.now_ms()
            if utc_ms is not None:
                update_msg["utc_ms"] = utc_ms
        update_msg.update(data)
        update_json = json.dumps(update_msg)
        self.uart_.write(update_json)
        self.uart_.write("\r\n")

    def poll_commands(self):
        """Returns the commands (dicts with a "cmd" key) received since the last call."""
        commands = []
        n = self.uart_.any()
        if not n:
            return commands
        for b in self.uart_.read(n) or b'':
            if b == 0x0A:
                if not self.rx_bad_:
                    command = self._parse(bytes(self.rx_))
                    if command is not None:
                        commands.append(command)
                self.rx_ = bytearray()
                self.rx_bad_ = False
            elif b == 0x0D:
                pass
            elif 0x20 <= b < 0x7F and len(self.rx_) < MAX_COMMAND:
                self.rx_.append(b)
            else:
                # Noise or an overlong line: drop the whole line rather than
                # risk splicing what's left into a valid-looking command.
                self.rx_bad_ = True
        return commands

    @staticmethod
    def _parse(line):
        line = line.strip()
        if not line.startswith(b'{'):
            return None
        try:
            message = json.loads(line)
        except ValueError:
            return None
        if isinstance(message, dict) and isinstance(message.get("cmd"), str):
            return message
        return None
