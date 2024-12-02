from serial import Serial
import json
import time

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client import Point
import gpsd

bucket = "roboat_01"
org = "CSO"
token = "TIGyIXb1Q1Otd_R2VMXzE7vLKpVHAFmchxwyB3-Opr1jFBRSP1IVGQKKFXNm1GBZEOBqmzF3H1oA0R3Z-PqIHA=="
# Store the URL of your InfluxDB instance
url="http://localhost:8086"

gps_interval_ns = 1e9
gps_connect_needed = True

if __name__ == "__main__":

    ser = Serial('/dev/ttyAMA3', 115200, timeout=0)

    client = influxdb_client.InfluxDBClient(
        url=url,
        token=token,
        org=org
    )

    # Initialize SYNCHRONOUS instance of WriteApi
    write_api = client.write_api(write_options=SYNCHRONOUS)

    gps_next_readtime = time.monotonic_ns()
    buf = ""

    # main loop
    while True:
        now = time.monotonic_ns()
        read_data = False
        
        # first job: read off data coming in from the RP2040
        s = ser.read()
        while len(s) > 0:
            read_data = True
            if s[0] == 0xff:
                break
            one_char = s.decode("utf-8")
            s = ser.read()
            if one_char != "\r":
                if one_char == "\n":
                    try:
                        data = json.loads(buf)
                    except json.decoder.JSONDecodeError as err:
                        print(err)
                        print("Bad buffer: |{}|".format(buf))
                    buf = ""
                    print(data)

                    if data['src'] == "mppt":               
                        dictionary = {
                            "measurement": "mppt",
                            "fields": {
                                "solar_v": data["sol_v"],
                                "solar_p": data["sol_p"],
                                "tracker_mode": int(data["mppt_mode"]),
                                "epoch": data["mppt_epoch"],
                                "load_i": data["load_i"],
                                "batt_v": data["batt_v"],
                                "batt_i": data["batt_i"],
                                "total_energy": data["mppt_total_kwh"]
                            },
                            # "time": 1
                        }
                        write_api.write(bucket, org, dictionary)
                    elif data['src'] == "ina260":
                        dictionary = {
                            "measurement": "ina260",
                            "fields": {
                                "logic_p": data["logic_p"],
                                "logic_i": data["logic_i"],
                                "batt_v": data["batt_v"],
                                "logic_total_ah": data["logic_total_ah"]
                            },
                            # "time": 1
                        }
                        write_api.write(bucket, org, dictionary)

                else:
                    buf += one_char
        
        # then see if it's time to read from the gps
        if gps_next_readtime < now:
            gps_next_readtime = gps_next_readtime + gps_interval_ns
            read_data = True
            fields = {
                "error": 0
            }
            if gps_connect_needed:
                try:
                    gpsd.connect()
                    gps_connect_needed = False
                except UserWarning as w:
                    fields["error"] = 1
                    fields["error_msg"] = str(w)
                    
            try:
                packet = gpsd.get_current()
                fields["mode"] = packet.mode
                fields["sats"] = packet.sats
                if packet.mode >= 2:
                    fields["lat"] = float(packet.lat)
                    fields["lon"] = float(packet.lon)
                    fields["hspeed"] = float(packet.hspeed)
                    fields["track"] = float(packet.track)
                    fields["time"] = packet.time
                if packet.mode >= 3:
                    fields["alt"] = float(packet.alt)
                    fields["climb"] = float(packet.climb)
            except UserWarning as w:
                    fields["error"] = 1
                    fields["error_msg"] = str(w)

            dictionary = {
                "measurement": "gps",
                "fields": fields
            }
            write_api.write(bucket, org, dictionary)

        # if not read_data:
        time.sleep(0.1)
