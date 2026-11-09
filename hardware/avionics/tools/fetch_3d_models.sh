#!/bin/sh
# Downloads the makers' 3D models of the socketed modules into lib/3d/ (gitignored).
# The footprints in lib/roboat.pretty and the Feather's footprint refer to these files.
# Without them KiCad's 3D view just leaves those modules out.
set -eu
cd "$(dirname "$0")/../lib"
mkdir -p 3d
fetch() {  # fetch URL FILE
    if [ -s "3d/$2" ]; then echo "have 3d/$2"; return; fi
    curl -fsSL -A "Mozilla/5.0" -o "3d/$2.part" "$1"
    mv "3d/$2.part" "3d/$2"
    echo "got 3d/$2"
}
# Pololu, from each product's Resources tab (items 3782 and 5593)
fetch https://www.pololu.com/file/0J1660/d36v28fx-step-down-voltage-regulators.step Pololu_D36V28F5.step
fetch https://www.pololu.com/file/0J2201/d24v7fx-step-down-voltage-regulators.step Pololu_D24V7F5.step
# Adafruit, from github.com/adafruit/Adafruit_CAD_Parts (MIT)
fetch "https://raw.githubusercontent.com/adafruit/Adafruit_CAD_Parts/main/4884%20Feather%20RP2040/4884%20Feather%20RP2040.step" Adafruit_Feather_RP2040.step
