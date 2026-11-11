#!/usr/bin/env python3
"""Draws the Raspberry Pi 4 under this board, for stacking the board on the Pi.

Adds, as one group:
  - the Pi's outline and main parts on User.Drawings, from Raspberry Pi's own
    mechanical drawing (RP-008342-DS, the Pi 4 DXF);
  - its four M2.5 mounting holes, as board-only footprints H1-H4;
  - J2 moved and turned so its pins meet the Pi's header;
  - a cutout in the board above the CPU;
  - a keepout (no tracks, vias, pads or pours, on either layer) above the
    Pi's WiFi antenna.
Moving the group in KiCad moves all of these together. The board's own outline
(Edge.Cuts) is left alone: draw it to suit, keeping clear of the Pi's USB and
Ethernet ports, which stand taller than the header stack.

Run it with KiCad's own Python while the board is closed in KiCad:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      tools/add_pi4_outline.py avionics.kicad_pcb [X Y]
X, Y is where the Pi's top-left corner goes, in mm (default 100, 130).
Run it once: it stops if the board already has the group.

  python3 tools/add_pi4_outline.py avionics.kicad_pcb --antenna
adds only the antenna and its keepout to a board that already has the group,
finding the Pi from its mounting holes. It stops if the keepout is there.
"""
import sys

import pcbnew

MM = pcbnew.FromMM

# Pi 4 coordinates from the DXF: origin at the lower-left corner, Y up, with the
# GPIO header along the top edge and the USB and Ethernet ports on the right.
PI_W, PI_H, CORNER = 85.0, 56.0, 3.0
HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
PIN1 = (8.37, 51.23)  # pin 2 is 2.54 mm nearer the edge, pin 3 is 2.54 mm right
CPU = (21.75, 25.0, 36.75, 40.0)  # BCM2711, 15 x 15 mm
CUTOUT_MARGIN = 1.0  # cutout is the CPU plus this much on every side
CUTOUT_CORNER = 1.0

# Main parts on the Pi's top (bounding boxes from the DXF's PARTS_TOP layer).
PARTS = [
    ("GPIO header", (7.1, 50.0, 57.9, 55.0)),
    ("Ethernet", (66.65, 37.99, 88.0, 53.51)),
    ("USB", (70.5, 20.43, 88.0, 34.25)),
    ("USB", (70.3, 1.65, 88.0, 15.57)),
    ("CPU", CPU),
    ("RAM", (39.05, 25.0, 50.55, 40.0)),
    ("WiFi", (6.6, 36.1, 17.4, 49.1)),
    ("USB ctrl", (55.5, 20.0, 63.5, 28.0)),
    ("DSI", (1.5, 16.8, 5.45, 39.2)),
    ("CSI", (45.05, 0.3, 49.0, 22.7)),
    ("USB-C", (6.88, -1.25, 15.53, 6.15)),
    ("HDMI0", (22.4, -1.43, 29.6, 6.52)),
    ("HDMI1", (35.9, -1.43, 43.1, 6.52)),
    ("Audio", (50.5, 0.0, 57.5, 12.5)),
]
NOTE = ("Raspberry Pi 4 below this board (RP-008342-DS).",
        "Ethernet and USB stand taller than the 11 mm header stack.")

# The WiFi antenna: the strip between the board's left edge and the WiFi can.
# The DXF has no copper, so this is inferred from the parts around it (its
# matching parts at the edge, Proant's licence text just below, the can, and
# the mounting hole above).
ANTENNA = (0.0, 39.3, 6.6, 50.0)
# No copper on our board above it, on either layer. It reaches well past the
# Pi's left edge to cover an overhang there, and stops short of J2's pin 1.
KEEPOUT = (-20.0, 37.5, 7.5, 50.0)
KEEPOUT_NAME = "Pi WiFi antenna"

GROUP = "Raspberry Pi 4 (below)"
HOLE_LIB ="/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty"
HOLE_FP = "MountingHole_2.7mm_M2.5"


def pi_origin(board):
    """The Pi's top-left corner, found from mounting holes H1 and H3."""
    h1 = board.FindFootprintByReference("H1")
    h3 = board.FindFootprintByReference("H3")
    if not (h1 and h3):
        sys.exit("The board has no H1 and H3 to find the Pi by")
    p1, p3 = h1.GetPosition(), h3.GetPosition()
    if p1.x != p3.x:
        sys.exit("H1 and H3 aren't aligned: the Pi seems rotated, which this doesn't handle")
    (x1, y1), (x3, y3) = HOLES[0], HOLES[2]
    return pcbnew.ToMM(p1.x) - x1, pcbnew.ToMM(p3.y) - (PI_H - y3)


def main(path, ox=100.0, oy=130.0, antenna_only=False):
    board = pcbnew.LoadBoard(path)
    existing = [g for g in board.Groups() if g.GetName() == GROUP]
    if antenna_only:
        if not existing:
            sys.exit(f"The board has no group '{GROUP}' to add the antenna to")
        if any(z.GetZoneName() == KEEPOUT_NAME for z in board.Zones()):
            sys.exit(f"The board already has the keepout '{KEEPOUT_NAME}'")
        ox, oy = pi_origin(board)
        print(f"Pi's top-left corner at ({ox:.2f}, {oy:.2f})")
        group = existing[0]
    else:
        # KiCad 10's Python bindings can't read a group's members back, so a
        # rerun can't tidy up after the last run. Move the group in KiCad instead.
        if existing:
            sys.exit(f"The board already has the group '{GROUP}'. Move it in KiCad, "
                     "or start again from a board without it.")
        group = pcbnew.PCB_GROUP(board)
        group.SetName(GROUP)
        board.Add(group)

    def at(x, y):  # Pi coordinates to board coordinates
        return pcbnew.VECTOR2I(MM(ox + x), MM(oy + PI_H - y))

    def add(item):
        board.Add(item)
        group.AddItem(item)
        return item

    def seg(a, b, layer, width):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(a)
        s.SetEnd(b)
        s.SetLayer(layer)
        s.SetWidth(MM(width))
        return s

    def arc(a, m, b, layer, width):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(a, m, b)
        s.SetLayer(layer)
        s.SetWidth(MM(width))
        return s

    def rounded(x0, y0, x1, y1, r, layer, width):
        """A rounded rectangle in Pi coordinates, as segments and arcs."""
        k = r * (1 - 0.5 ** 0.5)
        out = [
            seg(at(x0 + r, y0), at(x1 - r, y0), layer, width),
            seg(at(x1, y0 + r), at(x1, y1 - r), layer, width),
            seg(at(x1 - r, y1), at(x0 + r, y1), layer, width),
            seg(at(x0, y1 - r), at(x0, y0 + r), layer, width),
        ]
        if r:
            out += [
                arc(at(x1 - r, y0), at(x1 - k, y0 + k), at(x1, y0 + r), layer, width),
                arc(at(x1, y1 - r), at(x1 - k, y1 - k), at(x1 - r, y1), layer, width),
                arc(at(x0 + r, y1), at(x0 + k, y1 - k), at(x0, y1 - r), layer, width),
                arc(at(x0, y0 + r), at(x0 + k, y0 + k), at(x0 + r, y0), layer, width),
            ]
        return out

    def text(s, x, y, size, layer=pcbnew.Dwgs_User):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(at(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        return t

    def antenna():
        x0, y0, x1, y1 = ANTENNA
        for s in rounded(x0, y0, x1, y1, 0, pcbnew.Dwgs_User, 0.1):
            add(s)
        t = add(text("WiFi antenna", (x0 + x1) / 2, (y0 + y1) / 2, 0.8))
        t.SetTextAngleDegrees(90)

        x0, y0, x1, y1 = KEEPOUT
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetZoneName(KEEPOUT_NAME)
        z.SetLayerSet(pcbnew.LSET.AllCuMask())
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowFootprints(False)
        outline = z.Outline()
        outline.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            outline.Append(at(x, y))
        add(z)

    if antenna_only:
        antenna()
        board.Save(path)
        return

    # The Pi and its parts, for reference.
    for s in rounded(0, 0, PI_W, PI_H, CORNER, pcbnew.Dwgs_User, 0.2):
        add(s)
    for name, (x0, y0, x1, y1) in PARTS:
        for s in rounded(x0, y0, x1, y1, 0, pcbnew.Dwgs_User, 0.1):
            add(s)
        add(text(name, (x0 + x1) / 2, (y0 + y1) / 2, 1.2 if x1 - x0 > 6 else 0.8))
    add(text(NOTE[0], PI_W / 2, -5.0, 1.5))
    add(text(NOTE[1], PI_W / 2, -7.5, 1.5))

    # Mounting holes, which the board needs too.
    for i, (x, y) in enumerate(HOLES, 1):
        ref = f"H{i}"
        old = board.FindFootprintByReference(ref)
        if old:
            board.Remove(old)
        fp = pcbnew.FootprintLoad(HOLE_LIB, HOLE_FP)
        fp.SetFPID(pcbnew.LIB_ID("MountingHole", HOLE_FP))
        fp.SetReference(ref)
        fp.SetBoardOnly(True)
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        fp.SetPosition(at(x, y))
        add(fp)
        # Hide the label, which would sit off the board's edge. (Done after
        # adding: hiding it before had no effect.)
        fp.Reference().SetVisible(False)

    # J2 on the back, its pins on the Pi's header pins.
    j2 = board.FindFootprintByReference("J2")
    if not j2.IsFlipped():
        j2.Flip(j2.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    want = {"1": at(*PIN1), "2": at(PIN1[0], PIN1[1] + 2.54), "3": at(PIN1[0] + 2.54, PIN1[1])}
    for deg in (0, 90, 180, 270):
        j2.SetOrientationDegrees(deg)
        p = {n: j2.FindPadByNumber(n).GetPosition() for n in want}
        if p["2"] - p["1"] == want["2"] - want["1"] and p["3"] - p["1"] == want["3"] - want["1"]:
            break
    else:
        sys.exit("No rotation of J2 matches the Pi's header")
    j2.Move(want["1"] - j2.FindPadByNumber("1").GetPosition())
    for n in ("1", "2", "3", "40"):
        q = j2.FindPadByNumber(n).GetPosition()
        print(f"J2 pin {n} at ({pcbnew.ToMM(q.x):.2f}, {pcbnew.ToMM(q.y):.2f})")
    add(j2)

    # The cutout above the CPU.
    x0, y0, x1, y1 = CPU
    m = CUTOUT_MARGIN
    for s in rounded(x0 - m, y0 - m, x1 + m, y1 + m, CUTOUT_CORNER, pcbnew.Edge_Cuts, 0.1):
        add(s)

    antenna()
    board.Save(path)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--antenna" in args:
        args.remove("--antenna")
        main(args[0], antenna_only=True)
    else:
        main(args[0], *(float(a) for a in args[1:3]))
