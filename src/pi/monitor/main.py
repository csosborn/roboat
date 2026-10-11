from serial import Serial
import json
import os
import sys
import time

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

from points import to_point

bucket = "roboat_01"
org = "CSO"
url = os.environ.get("INFLUX_URL", "http://localhost:8086")
token = os.environ.get("INFLUX_TOKEN")
if not token:
    sys.exit("INFLUX_TOKEN is not set; see src/pi/monitor/monitor.env.example")

if __name__ == "__main__":

    ser = Serial('/dev/ttyAMA3', 115200, timeout=0)

    client = influxdb_client.InfluxDBClient(
        url=url,
        token=token,
        org=org
    )

    # Initialize SYNCHRONOUS instance of WriteApi
    write_api = client.write_api(write_options=SYNCHRONOUS)

    buf = ""

    # main loop
    while True:
        # read off data coming in from the RP2040
        s = ser.read()
        while len(s) > 0:
            if s[0] == 0xff:
                break
            one_char = s.decode("utf-8", errors="replace")
            s = ser.read()
            if one_char != "\r":
                if one_char == "\n":
                    try:
                        data = json.loads(buf)
                    except json.decoder.JSONDecodeError as err:
                        print(err)
                        print("Bad buffer: |{}|".format(buf))
                        buf = ""
                        continue
                    buf = ""
                    print(data)

                    try:
                        point = to_point(data)
                    except (KeyError, TypeError, ValueError) as err:
                        print("Unusable message ({!r}): {}".format(err, data))
                        continue
                    if point is not None:
                        write_api.write(bucket, org, point)
                else:
                    buf += one_char

        time.sleep(0.1)
