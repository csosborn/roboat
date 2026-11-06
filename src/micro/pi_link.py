import json
import time

MAX_COMMAND = 256
# The monitor sends a heartbeat every 2 s.
HEARTBEAT_TIMEOUT_MS = 10000


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
        self.latest = {}  # src -> the last message sent from that source

    def message(self, src, data):
        msg = {"offset_s": 0, "src": src}
        if self.clock_ is not None:
            utc_ms = self.clock_.now_ms()
            if utc_ms is not None:
                msg["utc_ms"] = utc_ms
        msg.update(data)
        return msg

    def send_update(self, src, data):
        msg = self.message(src, data)
        self.latest[src] = msg
        self.uart_.write(json.dumps(msg))
        self.uart_.write("\r\n")
        return msg

    def send_request(self, action, **fields):
        """Ask the Pi to do something. Never stored or replayed."""
        fields["action"] = action
        self.uart_.write(json.dumps(self.message("request", fields)))
        self.uart_.write("\r\n")

    def send_line(self, line):
        """Send an already-encoded message line (e.g. a stored record)."""
        self.uart_.write(line)

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


class PiPresence:
    """Whether the Pi's monitor is listening, judged by its heartbeats."""

    def __init__(self):
        self.last_ms_ = None
        self.listening = False

    def heard(self, now_ms):
        """Record a heartbeat. Returns True if the Pi was not listening before."""
        self.last_ms_ = now_ms
        came_back = not self.listening
        self.listening = True
        return came_back

    def check(self, now_ms):
        """Returns True when heartbeats have just stopped."""
        if self.listening and time.ticks_diff(now_ms, self.last_ms_) > HEARTBEAT_TIMEOUT_MS:
            self.listening = False
            return True
        return False
