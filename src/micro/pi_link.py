import json

class PiLink:

    def __init__(self, uart, clock=None):
        self.uart_ = uart
        self.clock_ = clock

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
