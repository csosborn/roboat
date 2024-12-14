#!/bin/bash
set -e

cd /workspace/micropython/ports/rp2
make BUILD=/build BOARD=ADAFRUIT_FEATHER_RP2040 USER_C_MODULES=/workspace/ulab/code/micropython.cmake
