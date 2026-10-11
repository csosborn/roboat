from pi_link import PiLink, MAX_COMMAND


class FakeUart:
    def __init__(self):
        self.incoming = b''
        self.out = b''

    def feed(self, data):
        self.incoming += data

    def any(self):
        return len(self.incoming)

    def read(self, n):
        data, self.incoming = self.incoming[:n], self.incoming[n:]
        return data

    def write(self, s):
        self.out += s.encode() if isinstance(s, str) else s


def test_command_received():
    uart = FakeUart()
    link = PiLink(uart)
    uart.feed(b'{"cmd": "maintenance"}\n')
    assert link.poll_commands() == [{"cmd": "maintenance"}]
    assert link.poll_commands() == []


def test_command_split_across_reads():
    uart = FakeUart()
    link = PiLink(uart)
    uart.feed(b'{"cmd": "main')
    assert link.poll_commands() == []
    uart.feed(b'tenance"}\r\n')
    assert link.poll_commands() == [{"cmd": "maintenance"}]


def test_noise_from_a_powered_off_pi_is_ignored():
    uart = FakeUart()
    link = PiLink(uart)
    uart.feed(b'\x00\x00\xff\xfe\x00garbage\n\x00\x00{"cmd"\x00: "x"}\n')
    assert link.poll_commands() == []
    uart.feed(b'\n{"cmd": "maintenance"}\n')
    assert link.poll_commands() == [{"cmd": "maintenance"}]


def test_overlong_line_is_dropped_whole():
    uart = FakeUart()
    link = PiLink(uart)
    uart.feed(b'{"cmd": "maintenance", "pad": "' + b'x' * MAX_COMMAND + b'"}\n')
    assert link.poll_commands() == []
    uart.feed(b'{"cmd": "maintenance"}\n')
    assert link.poll_commands() == [{"cmd": "maintenance"}]


def test_json_without_a_command_is_ignored():
    uart = FakeUart()
    link = PiLink(uart)
    uart.feed(b'{"src": "status"}\n[1, 2]\n{"cmd": 5}\n')
    assert link.poll_commands() == []
