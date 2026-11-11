# Libraries

- `Adafruit-Feather-RP2040.*`: from github.com/bluepylons/Adafruit-RP2040-KiCAD
  (commit 6cf2333, MIT). Two local changes: pin 3 (the second 3.3V pin) is passive
  rather than a power output, so ERC doesn't report the Feather's one rail as two
  outputs shorted together; and the footprint has 3D models added by
  `tools/generate_footprints.py` (see 3D models below).
- `roboat.kicad_sym`: symbols for the Pololu regulators and the INA260 breakout, and
  `Pi_Header_2x20_NoPin3` for J2 (KiCad's `Conn_02x20_Odd_Even` without pin 3, added
  by `tools/generate_footprints.py`).
  Pin numbers match the footprints' pad numbers.
- `roboat.pretty`: footprints for the socketed modules, written by
  `tools/generate_footprints.py`. Each one's origin is its pad 1, drawn from the
  module's top (component side).
  - `Pololu_D36V28F5`: from Pololu's drill guide `reg24g-drill.dxf` (item 3782).
    Pads 1-5 in a row: EN, VIN, GND, GND, VOUT; pad 6, PG, 0.1 in above EN. The
    corner holes are 2.4 mm non-plated, for M2 standoffs.
  - `Pololu_D24V7F5`: from Pololu's drill guide `reg35b-drill.dxf` (item 5593).
    Pads 1-3: VIN, GND, VOUT. No mounting holes.
  - `PinSocket_2x20_P2.54mm_Vertical_NoPin3`: KiCad's 2x20 socket with pad 3 removed, so
    5 V can reach pins 2 and 4 through the inner row. See "No pin 3" in `connections.md`.
  - The Pololu pin names were read off the real boards, and agree with the drawings.
  - `Adafruit_INA260_Breakout`: Adafruit product 4226, from the pad and hole positions in
    github.com/adafruit/Adafruit-INA260-PCB (`Adafruit INA260.brd`, CC BY-SA 3.0,
    designed by Bryan Siepert for Adafruit Industries).
    Header pins 1-8: VCC, GND, SCL, SDA, ALERT, VBUS, VIN+, VIN-. The two 5.08 mm
    pads at the terminal block repeat VIN+ (7) and VIN- (8); they are optional.
    The corner holes are 2.7 mm non-plated, for M2.5 standoffs.

## 3D models

Run `tools/fetch_3d_models.sh` once after cloning. It downloads the makers' STEP
models into `lib/3d/`, which git ignores: the Pololu regulators (from each
product's Resources tab on pololu.com) and the Feather RP2040 (from
github.com/adafruit/Adafruit_CAD_Parts, MIT). Without them KiCad's 3D view just
leaves those modules out.

Adafruit publishes no model of the INA260 breakout, so
`roboat.3dshapes/Adafruit_INA260_Breakout.wrl` is a plain block model (board,
terminal block, chip) made by `tools/generate_footprints.py`.

Each module's footprint also carries KiCad's stock female socket (on this board)
and male header (on the module) for each row, so the 3D view shows the whole stack.
It assumes 8.5 mm sockets and headers with 2.5 mm spacers, putting each module's
underside 11.0 mm above this board. If the parts bought differ, change `SOCKET_H`
and `SPACER_H` in the generator and rerun it:

    python3 tools/generate_footprints.py lib/roboat.pretty lib/Adafruit-Feather-RP2040.pretty/Adafruit-Feather-RP2040.kicad_mod
    kicad-cli fp upgrade --force -o /tmp/roboat.pretty lib/roboat.pretty && cp /tmp/roboat.pretty/*.kicad_mod lib/roboat.pretty/
