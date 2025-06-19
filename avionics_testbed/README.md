# Roboat Avionics Testbed

The avionics testbed is a subset of the electronics that will be present on the full Roboat, meant to support development and testing of sensors. At present its components include:

    - Adafruit Feather RP2040 development board, with attached battery
    - I2C-connected GPS
    - I2C-connected IMU and magnetometer (bno08x series)
    - 32x128 pixel 1-bit OLED display for simple status display (ssd1306)

All code is written in Micropython.

## Current Functionality

Read from GPS and IMU, and display a few key values to the OLED display.

