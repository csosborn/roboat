#!/usr/bin/env python3
"""Compares the KiCad schematic's netlist with connections.md.

Exits non-zero on any difference. Run it after every schematic edit.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
KICAD_CLI = os.environ.get("KICAD_APP", "/Applications/KiCad/KiCad.app") + "/Contents/MacOS/kicad-cli"


def listed_nets():
    text = (HERE / "connections.md").read_text()
    section = text.split("## Nets")[1].split("Deliberately unconnected")[0]
    nets = {}
    for line in section.splitlines():
        m = re.match(r"\| ([A-Z0-9_]+) \| (`.*?`) \|", line)
        if m:
            nets[m.group(1)] = set(re.findall(r"`([^`]+)`", m.group(2)))
    return nets


def schematic_nets():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "net.xml"
        subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out),
                        str(HERE / "avionics.kicad_sch")], check=True, capture_output=True)
        text = out.read_text()
    nets = {}
    for m in re.finditer(r'<net code="\d+" name="([^"]*)"[^>]*>(.*?)</net>', text, re.S):
        name = m.group(1).lstrip("/").replace("&quot;", '"')
        nodes = set()
        for n in re.finditer(r"<node ([^>]*?)/?>", m.group(2)):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', n.group(1)))
            # KiCad 10 writes a named pin's function as NAME_NUMBER.
            function = attrs.get("pinfunction", "").removesuffix("_" + attrs["pin"])
            nodes.add((attrs["ref"], attrs["pin"], function))
        nets[name] = nodes
    return nets


# Parts whose two ends are interchangeable: a reversed one is noted, not a problem.
REVERSIBLE = ("R", "F")


def unreverse(listed, actual):
    """Swaps the pins of reversible parts that are in the right nets but backwards."""
    notes = []
    where = {}
    for name, nodes in actual.items():
        for ref, pin, func in nodes:
            where[(ref, pin)] = (name, func)
    refs = {ref for ref, _ in where if re.fullmatch(r"(%s)\d+" % "|".join(REVERSIBLE), ref)}
    for ref in sorted(refs):
        a, b = where.get((ref, "1")), where.get((ref, "2"))
        if not a or not b or a[1] or b[1]:
            continue
        want1 = next((n for n, eps in listed.items() if f"{ref}.1" in eps), None)
        want2 = next((n for n, eps in listed.items() if f"{ref}.2" in eps), None)
        if want1 == b[0] and want2 == a[0] and a[0] != b[0]:
            actual[a[0]].discard((ref, "1", "")); actual[a[0]].add((ref, "2", ""))
            actual[b[0]].discard((ref, "2", "")); actual[b[0]].add((ref, "1", ""))
            notes.append(f"note: {ref} is reversed (harmless)")
    return notes


def main():
    listed, actual = listed_nets(), schematic_nets()
    for line in unreverse(listed, actual):
        print(line)
    problems = []
    for name, wanted in listed.items():
        found = actual.pop(name, None)
        if found is None:
            problems.append(f"{name}: not in the schematic")
            continue
        unmatched = set(found)
        for endpoint in wanted:
            ref, pin = endpoint.split(".", 1)
            match = next((n for n in unmatched if n[0] == ref and pin in (n[1], n[2])), None)
            if match is None:
                problems.append(f"{name}: {endpoint} is missing")
            else:
                unmatched.discard(match)
        for ref, pin, func in sorted(unmatched):
            if not ref.startswith("#"):
                problems.append(f"{name}: extra pin {ref}.{func or pin}")
    for name, nodes in actual.items():
        real = sorted(f"{r}.{f or p}" for r, p, f in nodes if not r.startswith("#"))
        if real and not name.startswith("unconnected-"):
            problems.append(f"net not in connections.md: {name} {real}")
    for line in problems:
        print(line)
    print(f"{len(listed)} nets checked, {len(problems)} problems")
    return 1 if problems else 0


sys.exit(main())
