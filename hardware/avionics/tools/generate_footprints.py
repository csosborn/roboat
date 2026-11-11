#!/usr/bin/env python3
"""Writes the footprints in lib/roboat.pretty for the socketed modules, and J2's
Pi header without pin 3: a footprint derived from KiCad's own 2x20 socket and a
matching symbol, added to lib/roboat.kicad_sym.

Usage: python3 tools/generate_footprints.py [output.pretty [feather.kicad_mod]]
       (default lib/roboat.pretty; the INA260's block model goes in the sibling roboat.3dshapes)
The STEP models come from tools/fetch_3d_models.sh.
Then normalise with: kicad-cli fp upgrade --force -o lib/roboat.pretty lib/roboat.pretty

Positions come from the makers' own files, in the board's top view (component
side up), with the origin at the board's lower-left corner and Y up:
- INA260: adafruit/Adafruit-INA260-PCB, "Adafruit INA260.brd" (Eagle, CC BY-SA 3.0,
  designed by Bryan Siepert for Adafruit Industries). Millimetres.
- D36V28F5: Pololu drill guide reg24g-drill.dxf and dimension diagram (item 3782). Inches.
- D24V7F5: Pololu drill guide reg35b-drill.dxf and dimension diagram (item 5593). Inches.
Each footprint's origin is its pad 1. Pin names on the Pololu boards were read off
the real modules and agree with the dimension diagrams.
"""
import os
import re
import sys
from pathlib import Path

IN = 25.4


def footprint(name, descr, tags, size, pads, holes=(), unit=1.0, ref_at=None, models=()):
    """size: (w, h) of the module board; pads: [(number, name, x, y, drill, dia)];
    holes: [(x, y, drill)] non-plated. All in `unit`, board coordinates, Y up.
    models: [(path, (x, y, z) offset in mm, z rotation in degrees)]."""
    p1 = pads[0]
    ox, oy = p1[2] * unit, p1[3] * unit

    def k(x, y):
        return round(x * unit - ox, 4), round(oy - y * unit, 4)

    w, h = size
    x0, y0 = k(0, 0)
    x1, y1 = k(w, h)
    o = [f'(footprint "{name}" (version 20240108) (generator "roboat")', '  (layer "F.Cu")',
         f'  (descr "{descr}")', f'  (tags "{tags}")']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = ref_at if ref_at else (cx, cy - 1)
    o.append(f'  (property "Reference" "REF**" (at {rx} {ry} 0) (layer "F.SilkS") '
             '(effects (font (size 1 1) (thickness 0.15))))')
    o.append(f'  (property "Value" "{name}" (at {round(x1 - 0.8, 4)} {cy} 90) (layer "F.Fab") '
             '(effects (font (size 0.6 0.6) (thickness 0.09))))')
    o.append('  (attr through_hole)')
    o.append(f'  (fp_rect (start {x0} {y1}) (end {x1} {y0}) (stroke (width 0.1) (type solid)) '
             '(fill none) (layer "F.Fab"))')
    for layer, d, wd in (("F.SilkS", 0.12, 0.12), ("F.CrtYd", 0.25, 0.05)):
        o.append(f'  (fp_rect (start {x0 - d} {y1 - d}) (end {x1 + d} {y0 + d}) '
                 f'(stroke (width {wd}) (type solid)) (fill none) (layer "{layer}"))')
    # pin-1 marker: a short silk line just outside the outline, beside pad 1
    o.append(f'  (fp_line (start -1.3 {y0 + 0.5}) (end 1.3 {y0 + 0.5}) '
             '(stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    where = {k(x, y) for _, _, x, y, _, _ in pads}
    first = True
    for num, pname, x, y, drill, dia in pads:
        X, Y = k(x, y)
        if (X, round(Y - 2.54, 4)) in where:  # a pad directly above: label to the left instead
            o.append(f'  (fp_text user "{pname}" (at {round(X - 1.1, 4)} {Y} 0) (layer "F.Fab") '
                     '(effects (font (size 0.5 0.5) (thickness 0.08)) (justify right)))')
            label = False
        else:
            label = True
        shape = "rect" if first and num == "1" else "circle"
        first = False
        o.append(f'  (pad "{num}" thru_hole {shape} (at {X} {Y}) (size {dia} {dia}) (drill {drill}) '
                 f'(layers "*.Cu" "*.Mask") (pinfunction "{pname}"))')
        if label:
            o.append(f'  (fp_text user "{pname}" (at {X} {Y - 1.3} 90) (layer "F.Fab") '
                     '(effects (font (size 0.5 0.5) (thickness 0.08)) (justify left)))')
    for x, y, drill in holes:
        X, Y = k(x, y)
        o.append(f'  (pad "" np_thru_hole circle (at {X} {Y}) (size {drill} {drill}) (drill {drill}) '
                 '(layers "*.Cu" "*.Mask"))')
    for path, (mx, my, mz), rz in models:
        o.append(f'  (model "{path}" (offset (xyz {mx} {my} {mz})) (scale (xyz 1 1 1)) (rotate (xyz 0 0 {rz})))')
    o.append(')')
    return name, "\n".join(o) + "\n"


HDR = (1.0, 1.7)  # 0.1 in header: drill, pad diameter (mm)

# 3D stacking: a standard 8.5 mm female socket on this board, and the module's male
# header resting on it with its 2.5 mm spacer. Change these to match the parts bought.
SOCKET_H = 8.5
SPACER_H = 2.5
MODULE_Z = SOCKET_H + SPACER_H  # height of the module board's underside
STOCK = "${KICAD10_3DMODEL_DIR}"
OWN = "${KIPRJMOD}/lib/3d"


def header_row(n, x, y):
    """Stock socket (on this board) and pin header (on the module) for a row of n pins
    starting at footprint position (x, y) mm and running in +x."""
    # Stock 1xN models run in -Y (down the screen); rotating -90 degrees runs them in +X.
    return [(f"{STOCK}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x{n:02d}_P2.54mm_Vertical.step",
             (x, -y, 0), -90),
            (f"{STOCK}/Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x{n:02d}_P2.54mm_Vertical.step",
             (x, -y, SOCKET_H), -90)]

FOOTPRINTS = [
    footprint(
        "Adafruit_INA260_Breakout",
        "Adafruit INA260 breakout (product 4226), socketed on a 1x8 0.1 in header. "
        "Optional 5.08 mm pads repeat VIN+/VIN- at the terminal block. M2.5 holes for standoffs. "
        "Geometry from adafruit/Adafruit-INA260-PCB (CC BY-SA 3.0).",
        "INA260 Adafruit 4226 breakout",
        (22.86, 22.86),
        [(str(i + 1), n, 2.54 * (i + 1), 2.54, *HDR) for i, n in
         enumerate(["VCC", "GND", "SCL", "SDA", "ALERT", "VBUS", "VIN+", "VIN-"])]
        + [("7", "VIN+", 8.89, 19.05, 1.1, 2.2), ("8", "VIN-", 13.97, 19.05, 1.1, 2.2)],
        holes=[(2.54, 20.32, 2.7), (20.32, 20.32, 2.7)],
        ref_at=(8.89, -9.5),
        models=header_row(8, 0, 0) + [("${KIPRJMOD}/lib/roboat.3dshapes/Adafruit_INA260_Breakout.wrl",
                                        (0, 0, MODULE_Z), 0)],
    ),
    footprint(
        "Pololu_D36V28F5",
        "Pololu D36V28Fx step-down regulator (items 3781-3789), socketed: 1x5 0.1 in row "
        "(EN, VIN, GND, GND, VOUT) plus PG 0.1 in above EN. M2 holes for standoffs. "
        "Geometry from Pololu's drill guide reg24g-drill.dxf.",
        "Pololu D36V28F5 regulator",
        (0.70, 0.80),
        [(str(i + 1), n, 0.25 + 0.1 * i, 0.05, *HDR) for i, n in
         enumerate(["EN", "VIN", "GND1", "GND2", "VOUT"])]
        + [("6", "PG", 0.25, 0.15, *HDR)],
        holes=[(0.085, 0.085, 2.4), (0.615, 0.715, 2.4)],
        unit=IN,
        # Pololu's model: origin at the board's lower-left corner, top view, underside at z = 0
        models=header_row(5, 0, 0) + header_row(1, 0, -2.54)
        + [(f"{OWN}/Pololu_D36V28F5.step", (-0.25 * IN, -0.05 * IN, MODULE_Z), 0)],
    ),
    footprint(
        "Pololu_D24V7F5",
        "Pololu D24V7Fx step-down regulator (items 5592-5597), socketed: 1x3 0.1 in row "
        "(VIN, GND, VOUT). Geometry from Pololu's drill guide reg35b-drill.dxf.",
        "Pololu D24V7F5 regulator",
        (0.34, 0.54),
        [(str(i + 1), n, 0.07 + 0.1 * i, 0.05, *HDR) for i, n in enumerate(["VIN", "GND", "VOUT"])],
        unit=IN,
        models=header_row(3, 0, 0) + [(f"{OWN}/Pololu_D24V7F5.step", (-0.07 * IN, -0.05 * IN, MODULE_Z), 0)],
    ),
]

KICAD_APP = Path(os.environ.get("KICAD_APP", "/Applications/KiCad/KiCad.app"))
KICAD_FOOTPRINTS = KICAD_APP / "Contents/SharedSupport/footprints"
KICAD_SYMBOLS = KICAD_APP / "Contents/SharedSupport/symbols"

# J2, the Pi's header, without pin 3: there's no copper at pin 3, so 5V_PI can reach
# pins 2 and 4 through the inner row. Pin 3's contact is pushed out of the real
# socket: it is the Pi's GPIO2 (I2C1 SDA), which must never touch the 5 V copper
# that runs there now. KiCad drops the number of a pad without copper, so the
# symbol loses pin 3 as well, keeping the schematic and the board in step.
NOPIN3_FOOTPRINT = "PinSocket_2x20_P2.54mm_Vertical_NoPin3"
NOPIN3_SYMBOL = "Pi_Header_2x20_NoPin3"


def socket_without_pin3():
    """KiCad's 2x20 socket footprint with pad 3 removed and its place marked."""
    stock = KICAD_FOOTPRINTS / "Connector_PinSocket_2.54mm.pretty/PinSocket_2x20_P2.54mm_Vertical.kicad_mod"
    text = stock.read_text()
    name = NOPIN3_FOOTPRINT
    text = text.replace('(footprint "PinSocket_2x20_P2.54mm_Vertical"', f'(footprint "{name}"', 1)
    text = text.replace('(property "Value" "PinSocket_2x20_P2.54mm_Vertical"', f'(property "Value" "{name}"', 1)
    text, n = re.subn(r'\(descr "([^"]*)"\)',
                      r'(descr "\1. Pin 3 removed: no copper there, and its contact pushed out of the socket")',
                      text, count=1)
    assert n == 1
    pad3 = re.compile(r'\t\(pad "3" thru_hole circle\n\t\t\(at ([-\d.]+) ([-\d.]+)\)\n.*?\n\t\)\n', re.S)
    m = pad3.search(text)
    assert m, "pad 3 not found in the stock footprint"
    x, y = m.group(1), m.group(2)
    marker = (f'\t(fp_circle (center {x} {y}) (end {float(x) + 0.85} {y}) '
              '(stroke (width 0.1) (type dash)) (fill no) (layer "F.Fab"))\n'
              f'\t(fp_text user "no pin" (at {x} {y} 0) (layer "F.Fab") '
              '(effects (font (size 0.4 0.4) (thickness 0.06))))\n')
    text = text[:m.start()] + marker + text[m.end():]
    return name, text


def header_symbol_without_pin3():
    """KiCad's Conn_02x20_Odd_Even symbol with pin 3 removed, defaulting to the footprint above."""
    stock = (KICAD_SYMBOLS / "Connector_Generic.kicad_sym").read_text()
    m = re.search(r'\t\(symbol "Conn_02x20_Odd_Even"\n', stock)
    end = stock.index('\n\t)\n', m.start()) + 4
    text = stock[m.start():end]
    text = text.replace('"Conn_02x20_Odd_Even', f'"{NOPIN3_SYMBOL}')
    text, n = re.subn(r'(\(property "Value" )"[^"]*"', rf'\1"{NOPIN3_SYMBOL}"', text, count=1)
    assert n == 1
    text, n = re.subn(r'(\(property "Footprint" )"[^"]*"', rf'\1"roboat:{NOPIN3_FOOTPRINT}"', text, count=1)
    assert n == 1
    text, n = re.subn(r'(\(property "Description" )"[^"]*"',
                      r'\1"Raspberry Pi 40-pin header, 2x20, without pin 3 (GPIO2): its socket contact is removed"',
                      text, count=1)
    assert n == 1
    pin3 = re.compile(r'\t\t\t\(pin passive line\n(?:(?!\t\t\t\(pin ).)*?\(number "3"\n.*?\n\t\t\t\)\n', re.S)
    text, n = pin3.subn("", text)
    assert n == 1, n
    return text


def add_symbol(lib_path, name, text):
    """Adds the symbol to the library, replacing any symbol of the same name."""
    lib = Path(lib_path).read_text()
    m = re.search(r'\(symbol "%s"' % re.escape(name), lib)
    if m:  # the symbol runs to the end of its line (this library is one symbol per line) or block
        start = lib.rindex("\n", 0, m.start()) + 1
        end = lib.index("\n(symbol", start) + 1 if "\n(symbol" in lib[start:] else lib.rindex("\n)")
        lib = lib[:start] + lib[end:]
    i = lib.rstrip().rindex(")")
    Path(lib_path).write_text(lib[:i].rstrip() + "\n" + text.strip() + "\n)\n")


FOOTPRINTS.append(socket_without_pin3())


def ina260_wrl():
    """A plain block model of the INA260 breakout: board, terminal block, chip.
    Footprint coordinates in mm (pad 1 at the origin, Y up), underside of the board at z = 0."""
    boxes = [  # centre x, y, z; size x, y, z; colour
        ((8.89, 8.89, 0.8), (22.86, 22.86, 1.6), (0.1, 0.1, 0.1)),        # board
        ((8.89, 17.0, 1.6 + 5.0), (10.2, 7.6, 10.0), (0.1, 0.5, 0.15)),   # 5.08 mm terminal block
        ((8.89, 8.0, 1.6 + 0.5), (3.0, 3.0, 1.0), (0.2, 0.2, 0.2)),       # INA260 (SOIC-ish)
    ]
    u = 1 / 2.54
    out = ["#VRML V2.0 utf8", "# Adafruit INA260 breakout (4226), approximate, made by tools/generate_footprints.py"]
    for (x, y, z), (w, h, d), (r, g, b) in boxes:
        out.append(f"Transform {{ translation {x*u:.4f} {y*u:.4f} {z*u:.4f} children [ Shape {{ "
                   f"appearance Appearance {{ material Material {{ diffuseColor {r} {g} {b} }} }} "
                   f"geometry Box {{ size {w*u:.4f} {h*u:.4f} {d*u:.4f} }} }} ] }}")
    return "\n".join(out) + "\n"


# Models for the Feather's (vendored) footprint, whose origin is the board's centre.
FEATHER_MODELS = (header_row(16, -19.05, 10.16) + header_row(12, -8.89, -10.16)
                  + [(f"{OWN}/Adafruit_Feather_RP2040.step", (-25.4, -11.43, MODULE_Z), 0)])


def add_models(path, models):
    """Replaces any model blocks in a footprint file with `models`."""
    import re
    text = Path(path).read_text()
    text = re.sub(r'\n\s*\(model "[^"]*".*?\n?\s*\)\)\)\)?', "", text, flags=re.S)
    blocks = "".join(f'\n  (model "{p}" (offset (xyz {x} {y} {z})) (scale (xyz 1 1 1)) (rotate (xyz 0 0 {rz})))'
                     for p, (x, y, z), rz in models)
    text = text.rstrip()
    assert text.endswith(")")
    Path(path).write_text(text[:-1].rstrip() + blocks + "\n)\n")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "lib/roboat.pretty")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in FOOTPRINTS:
        (out / f"{name}.kicad_mod").write_text(text)
        print("wrote", out / f"{name}.kicad_mod")
    shapes = out.parent / "roboat.3dshapes"
    shapes.mkdir(exist_ok=True)
    (shapes / "Adafruit_INA260_Breakout.wrl").write_text(ina260_wrl())
    print("wrote", shapes / "Adafruit_INA260_Breakout.wrl")
    sym = out.parent / "roboat.kicad_sym"
    add_symbol(sym, NOPIN3_SYMBOL, header_symbol_without_pin3())
    print("wrote", NOPIN3_SYMBOL, "in", sym)
    if len(sys.argv) > 2:  # also add the 3D models to the Feather's footprint file given
        add_models(sys.argv[2], FEATHER_MODELS)
        print("added models to", sys.argv[2])
