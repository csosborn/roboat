from serial import Serial
import json
import time

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

if __name__ == "__main__":

    ser = Serial('/dev/serial0', 115200, timeout=0)


    buf = ""
    while True:
        s = ser.read()
        if len(s) > 0:
            one_char = s.decode("utf-8")
            if one_char != "\r":
                if one_char == "\n":
                    try:
                        data = json.loads(buf)
                    except json.decoder.JSONDecodeError as err:
                        print(err)
                        print("Bad buffer: |{}|".format(buf))
                    buf = ""
                    print(data)
                else:
                    buf += one_char
        else:
            time.sleep(0.005)