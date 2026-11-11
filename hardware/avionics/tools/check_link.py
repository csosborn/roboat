#!/usr/bin/env python3
"""Checks the stern link: the cable between the avionics and stern boards.

  python3 tools/check_link.py

J10 on the avionics board and J1 on the stern board must carry the same nets on
the same pins, matching the pinout table under "Stern link" in the avionics
board's connections.md. Reads both schematics' netlists, so run it after either
schematic changes. Exits non-zero on any difference.
"""
import re
import sys
from pathlib import Path

from check_netlist import schematic_nets

HARDWARE = Path(__file__).resolve().parent.parent.parent
ENDS = (("avionics", "J10"), ("stern", "J1"))


def listed_pinout():
    text = (HARDWARE / "avionics" / "connections.md").read_text()
    section = text.split("## Stern link")[1].split("\n## ")[0]
    return {m.group(1): m.group(2)
            for m in re.finditer(r"^\| (\d+) \| ([A-Z0-9_]+) \|", section, re.M)}


def connector_pins(board, ref):
    """pin number -> net name, for one connector in a board's schematic."""
    pins = {}
    for net, nodes in schematic_nets(HARDWARE / board).items():
        for node_ref, pin, _ in nodes:
            if node_ref == ref:
                pins[pin] = "(unconnected)" if net.startswith("unconnected-") else net
    return pins


def main():
    listed = listed_pinout()
    ends = [(board, ref, connector_pins(board, ref)) for board, ref in ENDS]
    problems = []
    for board, ref, pins in ends:
        if not pins:
            problems.append(f"{board}: no {ref} in the schematic")
        for pin in sorted(set(pins) | set(listed), key=int):
            want, got = listed.get(pin), pins.get(pin)
            if want is None:
                problems.append(f"{board} {ref}.{pin}: {got}, but the pinout table has no pin {pin}")
            elif got != want:
                problems.append(f"{board} {ref}.{pin}: {got or 'no such pin'}, want {want}")
    width = max(len(n) for n in listed.values())
    print("Pin  " + "  ".join(f"{b} {r}".ljust(width) for b, r, _ in ends))
    for pin in sorted(listed, key=int):
        print(f"{pin:>3}  " + "  ".join(str(p.get(pin, "-")).ljust(width) for _, _, p in ends))
    for line in problems:
        print(line)
    print(f"{len(listed)} link pins checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
