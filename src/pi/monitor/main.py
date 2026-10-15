from serial import Serial
import os
import sys
import time

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

from link import LineReader, handle, heartbeat, make_request_handler
from timesync import ChronyRefclock
from writer import QueuedWriter

bucket = "roboat_01"
org = "CSO"
url = os.environ.get("INFLUX_URL", "http://localhost:8086")
token = os.environ.get("INFLUX_TOKEN")
if not token:
    sys.exit("INFLUX_TOKEN is not set; see src/pi/monitor/monitor.env.example")

PI_LINK_PORT = "/dev/ttyAMA3"
CHRONY_SOCK = os.environ.get("CHRONY_SOCK", "/run/chrony.rp2040.sock")
HEARTBEAT_INTERVAL_S = 2.0


if __name__ == "__main__":

    ser = Serial(PI_LINK_PORT, 115200, timeout=0.05)

    client = influxdb_client.InfluxDBClient(
        url=url,
        token=token,
        org=org
    )

    # Initialize SYNCHRONOUS instance of WriteApi
    write_api = client.write_api(write_options=SYNCHRONOUS)
    writer = QueuedWriter(lambda point: write_api.write(bucket, org, point))
    reader = LineReader()
    refclock = ChronyRefclock(CHRONY_SOCK)
    on_request = make_request_handler(writer)
    next_heartbeat = 0.0

    # main loop
    while True:
        # Block briefly for the first byte, then take whatever has arrived,
        # so lines are timestamped close to when they came in.
        data = ser.read(1)
        if data:
            data += ser.read(ser.in_waiting)
        arrived = time.time()
        for line in reader.feed(data):
            handle(line, arrived, writer, refclock, on_request)
        writer.flush()

        if time.monotonic() >= next_heartbeat:
            ser.write(heartbeat(writer.acked_seq))
            next_heartbeat = time.monotonic() + HEARTBEAT_INTERVAL_S
