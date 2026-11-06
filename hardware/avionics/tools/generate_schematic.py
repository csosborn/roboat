#!/usr/bin/env python3
"""Writes a first-draft avionics.kicad_sch from connections.md.

Every pin gets a net label rather than a drawn wire, so the draft is easy to
rearrange by hand. Once the schematic has been tidied in KiCad, it is the source
of truth for placement: don't run this again over it.
"""
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
KICAD_APP = Path(os.environ.get("KICAD_APP", "/Applications/KiCad/KiCad.app"))
KICAD_SYMBOLS = KICAD_APP / "Contents/SharedSupport/symbols"
NS = uuid.UUID("6f1d3c52-8a51-4f6a-9c1e-0a1b2c3d4e5f")
ROOT = str(uuid.uuid5(NS, "root"))
PROJECT = "avionics"

# ref: (lib_id, value, x, y)
PARTS = {
    # Power
    "J1": ("Connector_Generic:Conn_01x02", "Load input", 30, 50),
    "F1": ("Device:Fuse", "3 A slow-blow", 62, 50),
    "D2": ("Device:D_Zener", "SMBJ18A", 90, 50),
    "A2": ("roboat:Adafruit_INA260", "INA260 breakout", 135, 52),
    "C2": ("Device:C_Polarized", "33u 50V", 180, 50),
    "U1": ("roboat:Pololu_D24V7F5", "D24V7F5", 225, 50),
    "D1": ("Device:D_Schottky", "Schottky 1A", 275, 50),
    "U2": ("roboat:Pololu_D36V28F5", "D36V28F5", 225, 85),
    # Pi power switch and power-good
    "R1": ("Device:R", "10k", 30, 100),
    "Q1": ("Transistor_FET:BSS138", "BSS138", 62, 100),
    "R2": ("Device:R", "10k", 110, 90),
    "R3": ("Device:R", "15k", 110, 112),
    # Feather and its sense dividers
    "A1": ("Adafruit-Feather-RP2040:Adafruit-Feather-RP2040", "Feather RP2040", 90, 190),
    "R6": ("Device:R", "100k", 30, 145),
    "R7": ("Device:R", "100k", 30, 167),
    "C1": ("Device:C", "0.1u", 30, 190),
    "R4": ("Device:R", "10k", 30, 215),
    "R5": ("Device:R", "15k", 30, 237),
    # Pi
    "J2": ("Connector_Generic:Conn_02x20_Odd_Even", "Raspberry Pi header", 225, 190),
    "R8": ("Device:R", "1k", 170, 150),
    "R9": ("Device:R", "1k", 170, 175),
    # Sensors and Victron
    "J3": ("Connector_Generic:Conn_01x04", "VE.Direct", 300, 90),
    "J4": ("Connector_Generic:Conn_01x04", "STEMMA QT I2C1", 300, 115),
    "J5": ("Connector_Generic:Conn_01x04", "STEMMA QT I2C0", 300, 140),
    # Drive
    "Q2": ("Transistor_FET:BSS138", "BSS138", 335, 60),
    "R10": ("Device:R", "100k", 365, 60),
    "J9": ("Connector_Generic:Conn_01x02", "Drive relay input", 340, 90),
    "R11": ("Device:R", "1k", 345, 120),
    "R12": ("Device:R", "1k", 345, 145),
    "J6": ("Connector_Generic:Conn_01x03", "ESC", 385, 120),
    "J8": ("Connector_Generic:Conn_01x03", "Rudder servo", 385, 145),
    # Spares
    "J7": ("Connector_Generic:Conn_01x09", "Spare GPIO", 300, 200),
}

# Nets that nothing on the board marks as driven, as far as ERC can tell.
FLAGGED_NETS = {"VBUS_12V": (30, 275), "LOAD_FUSED": (70, 275)}

HEADINGS = [
    ("Power input and supplies", 20, 25),
    ("Pi power switch and power-good", 20, 75),
    ("Feather and sense dividers", 20, 130),
    ("Pi link and 40-pin header", 160, 130),
    ("Victron and I2C", 285, 75),
    ("Drive", 325, 40),
    ("Spare GPIO", 285, 165),
    ("Power flags (for ERC)", 20, 262),
]

CUSTOM_SYMBOLS = {
    "Pololu_D24V7F5": ("U", 5.08, [("VIN", "power_in", "L"), ("GND", "power_in", "L"), ("VOUT", "power_out", "R")]),
    "Pololu_D36V28F5": ("U", 7.62, [("VIN", "power_in", "L"), ("EN", "input", "L"), ("GND1", "power_in", "L"),
                                    ("GND2", "power_in", "L"), ("VOUT", "power_out", "R"), ("PG", "open_collector", "R")]),
    "Adafruit_INA260": ("A", 10.16, [("VIN+", "passive", "L"), ("VIN-", "passive", "L"), ("VCC", "power_in", "L"),
                                     ("GND", "power_in", "L"), ("SDA", "bidirectional", "R"), ("SCL", "bidirectional", "R"),
                                     ("ALERT", "open_collector", "R"), ("VBUS", "input", "R")]),
}


def snap(v):
    return round(v / 2.54) * 2.54


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def block_at(text, start):
    """Returns the balanced (...) starting at text[start]."""
    depth, i, in_str = 0, start, False
    while True:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1


def find_symbol(text, name):
    m = re.search(r'\(symbol "%s"\s' % re.escape(name), text)
    if not m:
        sys.exit("symbol not found: " + name)
    return block_at(text, m.start())


def custom_symbol(name):
    prefix, half_h_unused, pins = CUSTOM_SYMBOLS[name]
    left = [p for p in pins if p[2] == "L"]
    right = [p for p in pins if p[2] == "R"]
    rows = max(len(left), len(right))
    top = (rows - 1) * 2.54 / 2 + 2.54
    top = round(top / 1.27) * 1.27
    w = 10.16
    body = (f'(symbol "{name}_0_1" (rectangle (start -{w} {top:.2f}) (end {w} -{top:.2f}) '
            '(stroke (width 0.254) (type default)) (fill (type background))))')
    out, number = [], 1
    for side, group in (("L", left), ("R", right)):
        y = top - 2.54
        for pin, kind, _ in group:
            x, a = (-(w + 2.54), 0) if side == "L" else (w + 2.54, 180)
            out.append(f'(pin {kind} line (at {x:.2f} {y:.2f} {a}) (length 2.54) '
                       f'(name "{pin}" (effects (font (size 1.27 1.27)))) '
                       f'(number "{number}" (effects (font (size 1.27 1.27)))))')
            y -= 2.54
            number += 1
    def prop(k, v, y, hide=False):
        h = " (hide yes)" if hide else ""
        return f'(property "{k}" "{v}" (at 0 {y:.2f} 0) (effects (font (size 1.27 1.27)){h}))'
    return (f'(symbol "{name}" (exclude_from_sim no) (in_bom yes) (on_board yes) '
            + prop("Reference", prefix, top + 1.27) + prop("Value", name, -top - 1.27)
            + prop("Footprint", "", 0, True) + prop("Datasheet", "", 0, True) + prop("Description", "", 0, True)
            + body + f'(symbol "{name}_1_1" ' + " ".join(out) + "))")


def load_library(lib):
    if lib == "Adafruit-Feather-RP2040":
        return (HERE / "lib" / (lib + ".kicad_sym")).read_text()
    return (KICAD_SYMBOLS / (lib + ".kicad_sym")).read_text()


def flattened(lib_id):
    """The symbol's definition, as a schematic caches it."""
    lib, name = lib_id.split(":")
    if lib == "roboat":
        text = custom_symbol(name)
    else:
        source = load_library(lib)
        text = find_symbol(source, name)
        ext = re.search(r'\(extends "([^"]+)"\)', text)
        if ext:
            parent = find_symbol(source, ext.group(1))
            pname = ext.group(1)
            subs = []
            for m in re.finditer(r'\(symbol "%s_\d+_\d+"' % re.escape(pname), parent):
                subs.append(block_at(parent, m.start()).replace(f'"{pname}_', f'"{name}_', 1))
            heads = re.findall(r'\(pin_(?:numbers|names)\b', parent[:parent.index("(property")])
            head_text = " ".join(block_at(parent, parent.index(h)) for h in heads)
            text = text.replace(ext.group(0), head_text, 1)
            text = text[:text.rindex(")")] + "\n".join(subs) + ")"
    return text.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)


def pins_of(text):
    """(number, name, x, y, angle) for each pin in a symbol definition."""
    found = []
    for m in re.finditer(r"\(pin\s+\w+\s+\w+\s*\(at\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\d+)\)", text):
        pin = block_at(text, m.start())
        name = re.search(r'\(name\s+"([^"]*)"', pin).group(1)
        number = re.search(r'\(number\s+"([^"]*)"', pin).group(1)
        found.append((number, name, float(m.group(1)), float(m.group(2)), int(m.group(3))))
    return found


def property_offsets(text):
    offsets = {}
    for m in re.finditer(r'\(property\s+"([^"]+)"\s+"([^"]*)"\s*\(at\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\)', text):
        offsets[m.group(1)] = (float(m.group(3)), float(m.group(4)), float(m.group(5)), m.group(2))
    return offsets


def parse_nets():
    text = (HERE / "connections.md").read_text()
    section = text.split("## Nets")[1].split("Deliberately unconnected")[0]
    nets = {}
    for line in section.splitlines():
        m = re.match(r"\| ([A-Z0-9_]+) \| (`.*?`) \|", line)
        if m:
            nets[m.group(1)] = re.findall(r"`([^`]+)`", m.group(2))
    return nets


def font(size=1.27):
    return f"(font (size {size} {size}))"


def label(net, x, y, angle):
    if angle == 0:      # pin's end is to the left of the body
        rot, just = 180, "right bottom"
    else:
        rot, just = 0, "left bottom"
    return (f'(label "{net}" (at {x:.2f} {y:.2f} {rot}) (effects {font()} (justify {just})) '
            f'(uuid "{uid("label", net, x, y)}"))')


def instance(ref, lib_id, value, x, y, definition, pin_numbers, footprint=""):
    offs = property_offsets(definition)
    def prop(key, val, hide):
        ox, oy, rot, _ = offs.get(key, (0, 0, 0, ""))
        h = " (hide yes)" if hide else ""
        return (f'(property "{key}" "{val}" (at {x + ox:.2f} {y - oy:.2f} {rot:g}) '
                f'(effects {font()}{h}))')
    pins = " ".join(f'(pin "{n}" (uuid "{uid(ref, "pin", n)}"))' for n in pin_numbers)
    return (f'(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}") '
            + prop("Reference", ref, False) + prop("Value", value, False)
            + prop("Footprint", footprint, True) + prop("Datasheet", "", True) + prop("Description", "", True)
            + " " + pins
            + f' (instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1)))))')


def ground(ref_index, x, y, angle, definition):
    """A GND power symbol on a pin, pointing away from the part."""
    rot = {0: 270, 180: 90, 270: 180, 90: 0}[angle]
    ref = f"#PWR{ref_index:03d}"
    return (f'(symbol (lib_id "power:GND") (at {x:.2f} {y:.2f} {rot}) (unit 1) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}") '
            f'(property "Reference" "{ref}" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Value" "GND" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Footprint" "" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Datasheet" "" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Description" "" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(pin "1" (uuid "{uid(ref, "pin")}")) '
            f'(instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1)))))')


def pwr_flag(index, net, x, y):
    ref = f"#FLG{index:03d}"
    return (f'(symbol (lib_id "power:PWR_FLAG") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}") '
            f'(property "Reference" "{ref}" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Value" "PWR_FLAG" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Footprint" "" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Datasheet" "" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(property "Description" "" (at {x:.2f} {y:.2f} 0) (effects {font()} (hide yes))) '
            f'(pin "1" (uuid "{uid(ref, "pin")}")) '
            f'(instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1)))))')


def write_custom_library():
    body = "\n".join(custom_symbol(n) for n in CUSTOM_SYMBOLS)
    (HERE / "lib" / "roboat.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20241209) (generator "roboat_generate") (generator_version "9.0")\n'
        + body + "\n)\n")


def main():
    target = HERE / f"{PROJECT}.kicad_sch"
    if target.exists() and "--overwrite" not in sys.argv:
        sys.exit(f"{target.name} exists and may have hand edits. Pass --overwrite to replace it.")
    nets = parse_nets()
    endpoint_net = {e: n for n, es in nets.items() for e in es}
    missing = sorted({e.split(".")[0] for e in endpoint_net} - set(PARTS))
    if missing:
        sys.exit(f"no placement for: {missing}")

    definitions = {}
    for lib_id, *_ in PARTS.values():
        definitions.setdefault(lib_id, flattened(lib_id))
    for extra in ("power:GND", "power:PWR_FLAG"):
        definitions[extra] = flattened(extra)

    items, used, gnd_index = [], set(), 1
    for ref, (lib_id, value, x, y) in PARTS.items():
        x, y = snap(x), snap(y)
        definition = definitions[lib_id]
        pins = pins_of(definition)
        footprint = ""
        if ref == "A1":
            footprint = "Adafruit-Feather-RP2040:Adafruit-Feather-RP2040"
        items.append(instance(ref, lib_id, value, x, y, definition, [p[0] for p in pins], footprint))
        for number, name, px, py, angle in pins:
            net = endpoint_net.get(f"{ref}.{number}") or endpoint_net.get(f"{ref}.{name}")
            key = f"{ref}.{number}" if f"{ref}.{number}" in endpoint_net else f"{ref}.{name}"
            sx, sy = x + px, y - py
            if net is None:
                items.append(f'(no_connect (at {sx:.2f} {sy:.2f}) (uuid "{uid("nc", ref, number)}"))')
            elif net == "GND":
                used.add(key)
                items.append(ground(gnd_index, sx, sy, angle, definition))
                gnd_index += 1
            else:
                used.add(key)
                if angle in (90, 270):
                    # Keep the text of a vertical part's label clear of its lead.
                    items.append(f'(wire (pts (xy {sx:.2f} {sy:.2f}) (xy {sx + 2.54:.2f} {sy:.2f})) '
                                 f'(stroke (width 0) (type default)) (uuid "{uid("stub", ref, number)}"))')
                    sx += 2.54
                items.append(label(net, sx, sy, angle))
    unused = sorted(set(endpoint_net) - used)
    if unused:
        sys.exit(f"endpoints with no matching symbol pin: {unused}")

    for i, (net, (x, y)) in enumerate(FLAGGED_NETS.items(), 1):
        x, y = snap(x), snap(y)
        items.append(pwr_flag(i, net, x, y))
        if net == "GND":
            items.append(ground(gnd_index, x, y, 90, None))
            gnd_index += 1
        else:
            items.append(label(net, x, y, 180))

    for text, x, y in HEADINGS:
        items.append(f'(text "{text}" (exclude_from_sim no) (at {x} {y} 0) (effects {font(2)} '
                     f'(justify left bottom)) (uuid "{uid("text", text)}"))')

    lib_symbols = "\n".join(definitions.values())
    sch = (f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") '
           f'(uuid "{ROOT}") (paper "A3")\n'
           '(title_block (title "Roboat avionics board") (comment 1 "First draft, generated from connections.md"))\n'
           f'(lib_symbols\n{lib_symbols}\n)\n'
           + "\n".join(items)
           + '\n(sheet_instances (path "/" (page "1")))\n(embedded_fonts no)\n)\n')
    (HERE / f"{PROJECT}.kicad_sch").write_text(sch)
    write_custom_library()
    (HERE / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "roboat")(type "KiCad")(uri "${KIPRJMOD}/lib/roboat.kicad_sym")(options "")(descr "Modules for this board"))\n'
        '  (lib (name "Adafruit-Feather-RP2040")(type "KiCad")(uri "${KIPRJMOD}/lib/Adafruit-Feather-RP2040.kicad_sym")(options "")(descr ""))\n'
        ')\n')
    (HERE / "fp-lib-table").write_text(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "Adafruit-Feather-RP2040")(type "KiCad")(uri "${KIPRJMOD}/lib/Adafruit-Feather-RP2040.pretty")(options "")(descr ""))\n'
        ')\n')
    pro = HERE / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text('{\n  "meta": {"filename": "avionics.kicad_pro", "version": 3},\n  "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []}\n}\n')
    # Save in the installed KiCad's native format.
    subprocess.run([str(KICAD_APP / "Contents/MacOS/kicad-cli"), "sch", "upgrade", "--force",
                    str(HERE / f"{PROJECT}.kicad_sch")], check=True, capture_output=True)
    print(f"{len(PARTS)} parts, {len(nets)} nets")


main()
