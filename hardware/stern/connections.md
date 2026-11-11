# Stern board: connection list

A small board in the stern, where the ESC and rudder servo are. The avionics
board (`hardware/avionics/`) drives it over a 6-pin JST-PH cable, the stern link.
The ESC's BEC powers the servo here, so servo current never travels up the cable.
The board also carries 1-Wire temperature probes, for the ESC's enclosure and the
water outside, and a divider that lets the RP2040 see whether the BEC is up.

As for the avionics board, this file is the reference: change it first, then the
schematic, then run `python3 ../avionics/tools/check_netlist.py --board .` and
KiCad's ERC. `../avionics/tools/check_link.py` checks the stern link: that J1
here and the avionics board's J10 carry the same nets on the same pins.

## Approach

- Only logic signals and one small, current-limited supply cross the cable.
- BEC_5V stays on this board: ESC to servo, with a bulk capacitor at the servo.
- Pinouts match the avionics board's old J6 and J8, so the ESC lead and servo
  plug in as before.

## Parts

| Ref | Part | Mounting | Notes |
|---|---|---|---|
| J1 | Stern link, JST-PH 6 pins | B6B-PH-K (vertical) or S6B-PH-K (side entry) | Same pinout as the avionics board's J10, pin for pin. |
| J2 | ESC servo lead, 3 pins | 0.1 in | 1 = GND, 2 = BEC 5 V, 3 = signal. Brings the ESC's BEC output onto the board. |
| J3 | Rudder servo, 3 pins | 0.1 in | Same pinout as J2. Powered only from the BEC. |
| J4 | Temperature probe, 3 pins | Screw terminal or 0.1 in | 1 = GND, 2 = DQ, 3 = VDD. For a waterproof DS18B20 probe in the ESC's enclosure. |
| J5 | Water temperature probe, 3 pins | Screw terminal or 0.1 in | Same pinout as J4. For a waterproof DS18B20 probe against the hull or through it. |
| U1 | DS18B20, TO-92 | Soldered, optional | Not fitted unless wanted: measures the board instead of the enclosure. Shares the bus with the probes. |
| R1, R2 | 20k, 10k | Soldered | BEC sense divider, by 3: 1.67 V for 5 V, 2.47 V even for a 7.4 V BEC setting. |
| C1 | 470 uF, 16 V electrolytic | Soldered | Bulk capacitance at J3, to steady the BEC when the servo stalls or starts. 16 V covers BECs set to 7.4 V. |
| C2 | 0.1 uF | Soldered | Sensor supply decoupling, between J4 and J5. |
| H1, H2 | M3 mounting holes | | |

## Nets

| Net | Connects | Notes |
|---|---|---|
| GND | `J1.5` `J2.1` `J3.1` `J4.1` `J5.1` `U1.1` `R2.2` `C1.2` `C2.2` | One pour. The servo's return runs J3 to J2 here, not up the cable. |
| SENSOR_5V | `J1.1` `J4.3` `J5.3` `U1.3` `C2.1` | From the avionics board's 5V_AON, through its R13. |
| ONEWIRE | `J1.2` `J4.2` `J5.2` `U1.2` | The pull-up is on the avionics board. |
| DRIVE_PWM_R | `J1.3` `J2.3` | ESC signal, already through the avionics board's R11. |
| RUDDER_PWM_R | `J1.4` `J3.3` | Servo signal, already through the avionics board's R12. |
| BEC_5V | `J2.2` `J3.2` `R1.1` `C1.1` | Live only while the ESC is on. Never connect it to SENSOR_5V. |
| BEC_SENSE | `J1.6` `R1.2` `R2.1` | To GPIO27 on the avionics board. |

Deliberately unconnected: nothing.

## Layout requirements

- **J2 and J3:** side by side, with C1 between them, so servo current flows in a
  short loop that keeps to this board.
- **BEC_5V and SENSOR_5V:** keep them well apart. The two supplies must never meet.
- **R1 and R2:** near J1, so only the divided signal runs to the cable.
- **J4 and J5:** at a board edge, for the probes' leads.

## Open questions

1. **Cable length and routing:** the run from the avionics board to the stern
   decides whether R14 on the avionics board should drop to 2.2k.
2. **Enclosure:** whether this board sits in the ESC's own enclosure, which would
   make U1 measure the right thing and J4 unnecessary.
3. **Servo connector:** 0.1 in headers match today's leads. A locking connector
   would hold better against vibration.
