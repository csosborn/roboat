#!/bin/bash
set -e

cd /workspace/micropython/ports/rp2
echo "#define MICROPY_HW_FLASH_TYPE_LITTLEFS 1" >> boards/ADAFRUIT_FEATHER_RP2040/mpconfigboard.h 
make BUILD=/build BOARD=ADAFRUIT_FEATHER_RP2040 USER_C_MODULES=/workspace/ulab/code/micropython.cmake PICOTOOL_FETCH_FROM_GIT_PATH=1
