import json

class PiLink:

    def __init__(self, uart):
        self.uart_ = uart

    def send_update(self, src, data):
        update_msg = {
            "offset_s": 0,
            "src": src
        }
        update_msg.update(data)
        update_json = json.dumps(update_msg)
        self.uart_.write(update_json)
        self.uart_.write("\r\n")
