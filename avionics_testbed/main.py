from machine import Pin, I2C
import time
from lib.hardware import ssd1306
from neopixel import NeoPixel
from lib.hardware.micropyGPS import MicropyGPS
from lib.utils.soc_estimator import LFPSoCEstimator
from lib.hardware import bno08x
from lib.utils.avionics_logger import AvionicsLogger

np_pin = Pin(16, Pin.OUT)
np = NeoPixel(np_pin, 1)
np[0] = (0, 0, 0)
np.write()

batt_soc = LFPSoCEstimator()

i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400_000)

gps_i2c_addr = 16
display_i2c_addr = 60
bno085_addr = 74

print(i2c.scan())

bno = bno08x.BNO08X(i2c)

bno.set_quaternion_euler_vector(bno08x.BNO_REPORT_ROTATION_VECTOR)

# bno.enable_feature(bno08x.BNO_REPORT_ACCELEROMETER)
bno.enable_feature(bno08x.BNO_REPORT_ROTATION_VECTOR)

display = ssd1306.SSD1306_I2C(128, 32, i2c)
display.fill(0)
display.text("Hi there.", 30, 12, 1)
display.rect(0, 0, 128, 32, 1)
display.show()

time.sleep(1)

display.fill(0)
display.show()

gps = MicropyGPS(local_offset=-7)

# Initialize logger
logger = AvionicsLogger(max_files=100, file_size_kb=32)

IMU_SAMPLE_TIME_MS = 100
SOC_SAMPLE_TIME_MS = 1000
LOG_SAMPLE_TIME_MS = 1000  # Log once per second
last_imu_time = 0
last_soc_time = 0
last_log_time = 0
prev_logger_file = logger.current_file

while True:
    now = time.ticks_ms()
    byte = i2c.readfrom(gps_i2c_addr, 1)
    sentence = gps.update(byte.decode('ascii'))
    if sentence is not None:
        display.fill_rect(0, 0, 128, 24, 0)
        [ts_hour, ts_min, ts_sec] = gps.timestamp
        display.text(f"{ts_hour:02}:{ts_min:02}:{ts_sec:02}", 0, 0, 1)
        display.text(f"Log: {logger.current_file}", 0, 12, 1)
        display.show()
        
    if last_imu_time + IMU_SAMPLE_TIME_MS < now: 
        roll, tilt, pan = bno.euler
        display.fill_rect(0, 24, 128, 32, 0)
        display.text(f"{pan:.1f}", 0, 24, 1)
        display.show()
        
        err = abs(pan)
        last_imu_time = now

    # if last_soc_time + SOC_SAMPLE_TIME_MS < now:
    #     batt_soc.update(13.4, -.050, 25)
    #     print(f"{batt_soc.soc}")
    #     last_soc_time = now
        
    # Log data if we have a GPS fix and it's time to log
    if last_log_time + LOG_SAMPLE_TIME_MS < now and gps.valid:
        # Get UTC time from GPS
        utc_time = (
            gps.date[2],  # year
            gps.date[1],  # month
            gps.date[0],  # day
            gps.timestamp[0],  # hour
            gps.timestamp[1],  # minute
            gps.timestamp[2],  # second
            0  # millisecond (GPS doesn't provide this)
        )
        
        logger.log_data(
            lat=gps.latitude[0] + gps.latitude[1]/60.0,
            lon=gps.longitude[0] + gps.longitude[1]/60.0,
            gps_heading=gps.course,
            gps_speed=gps.speed[2],  # Speed in knots
            mag_heading=pan,  # Using the BNO's heading
            pitch=tilt,
            roll=roll,
            utc_time=utc_time
        )
        last_log_time = now

        if logger.current_file != prev_logger_file:
            prev_logger_file = logger.current_file
            np[0] = (0, 100, 100)
            np.write()
            time.sleep(0.1)
            np[0] = (0, 0, 0)
            np.write()
