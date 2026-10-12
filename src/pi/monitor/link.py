"""The Pi's side of the serial link to the RP2040: lines in, heartbeats out."""
import json
import subprocess

from points import to_point

MAX_LINE = 4096


class LineReader:
    """Splits the incoming byte stream into lines, dropping overlong ones."""

    def __init__(self):
        self.buf_ = b""

    def feed(self, data):
        self.buf_ += data
        *lines, self.buf_ = self.buf_.split(b"\n")
        if len(self.buf_) > MAX_LINE:
            self.buf_ = b""
        return [line.rstrip(b"\r").decode("utf-8", errors="replace")
                for line in lines if len(line) <= MAX_LINE]


def heartbeat(acked_seq):
    """The heartbeat the RP2040 listens for, acknowledging replayed records."""
    msg = {"cmd": "hb"}
    if acked_seq is not None:
        msg["ack"] = acked_seq
    return (json.dumps(msg) + "\n").encode()


def handle(line, arrived, writer, refclock, on_request=None):
    try:
        data = json.loads(line)
    except json.decoder.JSONDecodeError as err:
        print(err)
        print("Bad buffer: |{}|".format(line))
        return
    if not isinstance(data, dict):
        return
    print(data)

    replayed = "seq" in data
    if data.get("src") == "request":
        # Requests are acted on live only; a replayed one is stale by definition.
        if not replayed and on_request is not None:
            on_request(data)
        return
    if data.get("src") == "gps" and not replayed and isinstance(data.get("utc_ms"), int):
        refclock.send(arrived, data["utc_ms"] / 1000.0)

    try:
        point = to_point(data)
    except (KeyError, TypeError, ValueError) as err:
        print("Unusable message ({!r}): {}".format(err, data))
        return
    if point is not None:
        # Without the RP2040's GPS time, stamp on arrival so a point that
        # waits in the write queue keeps its real time.
        point.setdefault("time", int(arrived * 1e9))
        writer.write(point, seq=data.get("seq") if replayed else None)


def make_request_handler(writer, run=subprocess.run):
    """Acts on requests from the RP2040. A shutdown request powers the Pi off, once."""
    shutting_down = []

    def on_request(request):
        if request.get("action") != "shutdown" or shutting_down:
            return
        shutting_down.append(True)
        print("RP2040 requested shutdown ({}); powering off".format(request.get("reason")))
        writer.flush()
        run(["systemctl", "poweroff", "--no-block"], check=False)

    return on_request
