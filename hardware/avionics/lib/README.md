# Libraries

- `Adafruit-Feather-RP2040.*`: from github.com/bluepylons/Adafruit-RP2040-KiCAD
  (commit 6cf2333, MIT). One local change: pin 3 (the second 3.3V pin) is passive
  rather than a power output, so ERC doesn't report the Feather's one rail as two
  outputs shorted together.
- `roboat.kicad_sym`: symbols for the Pololu regulators and the INA260 breakout.
  Their pin numbers are placeholders until the footprints exist, because Pololu's
  pages don't give the physical pin order.
