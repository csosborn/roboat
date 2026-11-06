# Avionics board: connection list

This is the reference for the first custom PCB. It replaces the protoboard and
jumpers with the same circuit, plus the fixes the prototype showed we need. The
KiCad schematic gets checked against the nets table below, so change this file
first when the design changes.

After any schematic edit, run `python3 tools/check_netlist.py` and KiCad's ERC.
The checker compares KiCad's exported netlist with the table, and fails on any
difference. `tools/generate_schematic.py` wrote the first draft, and refuses to
overwrite the schematic unless told to.

Sources: the firmware on master (99fc6fa), `Compute.md`, measurements from
October-November 2026, and Pololu's product pages.

## Approach

- Keep the Feather and both converters socketed, so a failed module is a swap,
  not a rework. The first Feather's regulator failed in service.
- Copy the circuit that works. The firmware needs no changes for anything here,
  apart from the rudder output, which it doesn't have yet.
- Use the board itself to fix the wiring: a solid ground plane and a short, wide
  5 V path to the Pi.
- Leave open questions as headers and spare footprints, not decisions.

## Parts

| Ref | Part | Mounting | Notes |
|---|---|---|---|
| A1 | Adafruit Feather RP2040 | Socketed | Pin numbers are from the `Adafruit-Feather-RP2040` KiCad symbol (github.com/bluepylons/Adafruit-RP2040-KiCAD, MIT). Its LiPo stays on its own JST connector. |
| A2 | Adafruit INA260 breakout | Socketed | 0x40. Footprint needs checking against the real breakout. |
| U1 | Pololu D24V7F5 | Socketed | Always-on 5 V, 600 mA. VIN, GND, VOUT at 0.1 in. No reverse-voltage protection. |
| U2 | Pololu D36V28F5 | Socketed | Pi's 5 V. PG, EN, VIN, VOUT, GND, GND on a 0.1 in grid; PG isn't on the board edge. Two M2 holes. |
| Q1 | BSS138 | Soldered | Replaces the level shifter: it's the same circuit as the one channel in use. |
| Q2 | BSS138 | Soldered | New: switches the drive relay's input from 5 V. |
| R1 | 10k | Soldered | Holds GPIO11 high during an RP2040 reset. Don't raise this value (see below). |
| R2, R3 | 10k, 15k | Soldered | PG divider, about 3.04 V at the pin. |
| R4, R5 | 10k, 15k | Soldered | Victron TX divider, about 3.06 V at the pin. |
| R6, R7 | 100k, 100k | Soldered | LiPo divider. `LIPO_CAL` needs rechecking with the real parts. |
| R8, R9 | 1k | Soldered | New: series resistors on the Pi UART. |
| R10 | 100k | Soldered | New: holds Q2 off whenever GPIO7 isn't driving it, including with the Feather out of its socket. |
| R11, R12 | 1k | Soldered | New: series resistors on the ESC and rudder signals. |
| C1 | 0.1 uF | Soldered | At A0, as close to the socket pin as possible. |
| C2 | 33 uF, 50 V electrolytic | Soldered | New: at U1's VIN. Pololu warns of destructive LC spikes on U1, whose limit is 36 V. |
| D1 | Schottky, 1 A | Soldered | New: see open question 2. |
| D2 | SMBJ18A TVS | Soldered | New: clamps spikes from the motor sharing the load output, to about 29 V against U1's 36 V limit. Reverse polarity makes it conduct and blow F1. |
| F1 | Fuse, 3 A slow-blow (proposed) | Holder | New: covers the load input. Sized for the logic and Pi only, about 1 A. The ESC's feed never crosses the board. |
| J1 | Load input, 2 pins | Screw terminal or similar | From the Victron's load output, on its own wires. The ESC's relay taps the load output separately. 1 = +, 2 = GND. |
| J2 | Raspberry Pi 40-pin header | 2x20 female, underside | The board stacks on the Pi. Numbers are the Pi's physical pins. Mirrored in layout: see below. |
| J3 | VE.Direct, 4 pins | To match the Victron cable | 1 = GND, 2 = RX, 3 = TX, 4 = +5 V. Check against the real connector. |
| J4 | STEMMA QT (JST SH 4) | SMD | I2C1, for the GPS and IMU. 1 = GND, 2 = 3.3 V, 3 = SDA, 4 = SCL. |
| J5 | STEMMA QT (JST SH 4) | SMD | New: I2C0, so the IMU can leave the shared bus without a new board. Same pinout as J4. |
| J6 | ESC servo lead, 3 pins | 0.1 in | 1 = GND, 2 = BEC 5 V, 3 = signal. Carries the ESC's BEC output onto the board for the servo. |
| J7 | Spare GPIO header, 9 pins | 0.1 in | 1 = 3.3 V, 2 = GND, 3-9 = spare pins. |
| J8 | Rudder servo, 3 pins | 0.1 in | Same pinout as J6. Powered only from the BEC. |
| J9 | Drive relay input, 2 pins | 0.1 in or screw terminal | 1 = relay input +, 2 = relay input -. The relay itself stays off the board. |

## Nets

Status: **Built** is on the boat now. **Changed** is on the boat but altered
here. **New** is not on the boat yet.

| Net | Connects | Status | Notes |
|---|---|---|---|
| LOAD_IN | `J1.1` `F1.1` | New | Fuse added. |
| LOAD_FUSED | `F1.2` `A2.VIN+` `D2.K` | Changed | |
| VBUS_12V | `A2.VIN-` `U1.VIN` `U2.VIN` `C2.1` | Built | 12.0-14.2 V in normal use. C2 added. |
| GND | `J1.2` `U1.GND` `U2.GND1` `U2.GND2` `A1.4` `A2.GND` `C1.2` `C2.2` `D2.A` `Q2.S` `R10.2` `R3.2` `R5.2` `R7.2` `J2.6` `J2.9` `J2.14` `J2.20` `J2.25` `J2.30` `J2.34` `J2.39` `J3.1` `J4.1` `J5.1` `J6.1` `J7.2` `J8.1` | Changed | One plane. The prototype lost 0.29 V here at 1.5 A. |
| 5V_AON | `U1.VOUT` `D1.A` `J9.1` | Changed | Also feeds the drive relay's input, about 15 mA at most. |
| FEATHER_USB | `D1.K` `A1.26` | Changed | Feather's USB pin. Was fed directly. |
| 5V_PI | `U2.VOUT` `J2.2` `J2.4` `R2.1` | Changed | Target: at least 4.9 V at the Pi at 1.5 A. |
| 3V3 | `A1.2` `A1.3` `R1.1` `Q1.G` `A2.VCC` `J4.2` `J5.2` `J7.1` | Built | From the Feather's regulator. |
| LIPO_BAT | `A1.28` `R6.1` | Built | |
| LIPO_SENSE | `R6.2` `R7.1` `C1.1` `A1.5` | Built | GPIO26. |
| PI_EN_CTRL | `A1.23` `R1.2` `Q1.S` | Changed | GPIO11. High or floating = Pi on; low = Pi off. Same as today. |
| PI_EN | `Q1.D` `U2.EN` | Changed | Keep this trace short: high impedance, with a precise threshold. |
| PI_PG | `U2.PG` `R2.2` `R3.1` `A1.22` | Built | GPIO10. |
| VE_TX | `J3.3` `R4.1` | Built | Idles at 5.1 V. Must never reach the Feather undivided. |
| VE_TX_3V3 | `R4.2` `R5.1` `A1.21` | Built | GPIO9, UART1 RX. |
| PI_LINK_TX | `A1.15` `R8.1` | Changed | GPIO0, UART0 TX, 115200 baud. |
| PI_LINK_TX_R | `R8.2` `J2.29` | Changed | Pi GPIO5, RXD3 (`/dev/ttyAMA3`). |
| PI_LINK_RX | `A1.14` `R9.1` | Changed | GPIO1, UART0 RX. |
| PI_LINK_RX_R | `R9.2` `J2.7` | Changed | Pi GPIO4, TXD3. |
| I2C1_SDA | `A1.17` `A2.SDA` `J4.3` | Built | GPIO2, 400 kHz. GPS 0x10, INA260 0x40, IMU 0x4A. |
| I2C1_SCL | `A1.18` `A2.SCL` `J4.4` | Built | GPIO3. |
| I2C0_SDA | `A1.24` `J5.3` | New | GPIO12. |
| I2C0_SCL | `A1.25` `J5.4` | New | GPIO13. |
| DRIVE_PWR_EN | `A1.19` `Q2.G` `R10.1` | Changed | GPIO7, high = ESC on. Same polarity as today. |
| DRIVE_RELAY_N | `Q2.D` `J9.2` | New | |
| DRIVE_PWM | `A1.20` `R11.1` | Changed | GPIO8, 50 Hz; 1.5 ms is neutral. |
| DRIVE_PWM_R | `R11.2` `J6.3` | Changed | |
| RUDDER_PWM | `A1.16` `R12.1` | New | GPIO6. The pin is a proposal; the firmware has no rudder output yet. |
| RUDDER_PWM_R | `R12.2` `J8.3` | New | |
| BEC_5V | `J6.2` `J8.2` | New | Live only while the ESC is on. Never connect it to 5V_AON or 5V_PI. |
| SPARE_A1 | `A1.6` `J7.3` | New | GPIO27, ADC. |
| SPARE_A2 | `A1.7` `J7.4` | New | GPIO28, ADC. |
| SPARE_A3 | `A1.8` `J7.5` | New | GPIO29, ADC. |
| SPARE_D25 | `A1.10` `J7.6` | New | GPIO25. |
| SPARE_SCK | `A1.11` `J7.7` | New | GPIO18. |
| SPARE_MOSI | `A1.12` `J7.8` | New | GPIO19. |
| SPARE_MISO | `A1.13` `J7.9` | New | GPIO20. |

Deliberately unconnected:

| Pin | Why |
|---|---|
| `A1.1` RESET | The Feather's own button is enough. A reset counts as a cold start, so it holds the Pi off. |
| `A1.9` D24/GPIO24 | The firmware parks UART1's unused TX here. Connecting it would need a check of the Victron's RX levels. |
| `A1.27` ENABLE | Pulling it low would stop the Feather's 3.3 V regulator. |
| `J3.2` VE.Direct RX | The firmware only listens. |
| `J3.4` VE.Direct +5 V | The Victron's supply isn't needed. |
| `A2.ALERT`, `A2.VBUS` | Not used by the firmware. Keep the breakout's VBUS jumper as it is now. |
| `J2` pins 27 and 28 | Reserved for a HAT ID EEPROM, which this board doesn't have. |
| All other `J2` pins | The Pi's remaining GPIOs aren't used. |

## Pi power switch

R1 and Q1 are one channel of the level shifter, without the HV-side pull-up that
was left floating. The gate sits at 3.3 V, with GPIO11 on the source:

| GPIO11 | Q1 | EN | Pi supply |
|---|---|---|---|
| Driven high | Off | Pulled to VIN by U2's 100k | On |
| Floating or in reset (R1 holds it high) | Off | Pulled to VIN | On |
| Driven low | On | Near 0 V (below the 1.2 V threshold) | Off |
| Feather has no 3.3 V | Off | Pulled to VIN | On |

- Polarity and reset behaviour match today's, and deploys already prove the Pi
  rides through a reset, so the firmware doesn't change.
- A plain low-side FET with its gate on GPIO11 would work too, but it inverts
  the polarity, which means changing `boot.py`, `power_policy.py` and more.
- Q1 sinks about 0.14 mA at most, and sees the battery voltage on its drain. A
  BSS138 is rated for 50 V.
- **Don't raise R1.** In reset the RP2040's pin has a weak pull-down, which works
  against R1. With 10k the source stays near 3.3 V, so Q1 stays off. With 100k
  the source would sag, Q1 could turn on, and an RP2040 reset would cut the Pi.

## Drive power

GPIO7 switches a solid-state relay (the same type the Pi used to have) that
connects the ESC to the Victron's load output. Turning the ESC on also starts its
BEC, which will power the rudder servo.

| GPIO7 | Q2 | Relay | ESC and servo |
|---|---|---|---|
| Driven high | On | On | Powered |
| Driven low | Off | Off | Off |
| Floating or in reset | Off (R10) | Off | Off |
| Feather has no 3.3 V | Off (R10) | Off | Off |

- This is deliberately the opposite of the Pi's switch: an RP2040 reset should
  stop the motor, but not the Pi.
- Polarity matches today's, so the firmware doesn't change.
- GPIO7 drives the relay directly today, at 3.3 V and with a 4 mA default drive.
  The relay's input needs several mA, so that margin is thin. Q2 gives it a full
  5 V, with the current coming from U1 instead of the pin.
- BEC_5V only passes through the board from J6 to J8. Servo current stays on that
  path, away from the Pi's supply and the sensors.
- R11 and R12 limit current into an unpowered ESC or servo. **Firmware fix
  needed:** `enter_no_main_power` turns the relay off but leaves the ESC signal at
  1.5 ms once it's armed, so it keeps pulsing into an unpowered ESC. It should drop
  the signal low whenever the relay goes off.

## Stacking on the Pi

The board mounts rigidly on the 40-pin header, but it doesn't need to match the
Pi's outline. It can overhang as far as it likes, and can carry its modules on
either side.

- **Overhang away from the CPU:** the header runs along one long edge of the Pi.
  Extend the board outward past that edge, and it covers only a narrow strip of
  the Pi. The CPU stays uncovered, so no cutout is needed, a heatsink can be any
  height, and the Pi keeps the airflow it has now. Check the strip against
  Raspberry Pi's mechanical drawing, including the PoE pins beside the header.
- **Power path:** the even pins, including 5 V on pins 2 and 4, are in the row
  nearest the Pi's edge, so they face the overhang. U2 can sit right beside them,
  which makes the 5 V path very short. Five of the eight ground pins are in that
  row too.
- **Support:** the header can't carry a cantilever on a boat. Use standoffs at the
  Pi's two mounting holes along that edge (58 mm apart, M2.5), and add holes at the
  far corners of the overhang, fixed to the same base as the Pi.
- **J2 is on the underside:** a socket on the back of the board mirrors the pin
  order compared with the Pi's top view. Check it on a 1:1 print against a real
  Pi before ordering.
- **No fuse on the Pi side:** power through the 40-pin header bypasses the Pi's own
  input protection, so U2 and F1 are all that's guarding it.

## Layout requirements

Each of these comes from a fault on the prototype.

- **Ground:** a solid plane, with nothing routed through it between J1, U2 and
  J2.
- **Pi 5 V:** a short, wide pour from U2 to J2. Allow under 20 milliohms each
  way, about 30 mV at 1.5 A. Tie in all eight of J2's ground pins.
- **C1:** right at `A1.5`. On the prototype it sits about six inches of jumper
  away.
- **Victron divider:** R4 and R5 next to the Feather, so only the divided signal
  crosses the board near it.
- **U2's EN:** Q1 next to U2.
- **J6 and J8:** side by side, at the board edge, so servo current stays out of
  the rest of the plane.
- **D2 and C2:** close to J1 and U1, with short connections to the plane.
- **Test points:** VBUS_12V, 5V_AON, 5V_PI, 3V3, PI_EN, PI_PG and GND, each
  reachable with the Pi and modules fitted.

## Open questions

Settled on 2026-11-06:

- The board stacks on the 40-pin header, and may overhang the Pi.
- The INA260 is socketed.
- GPIO7 switches the ESC's relay.
- The ESC taps the load output directly, so motor current never touches the board,
  and the board's fuse doesn't cover it. The INA260 measures only the Pi and logic;
  the Victron's `load_i` shows the total. The motor's peak current is still to be
  measured, and needs checking against the load output's own limit.
- The Pi has no cooling yet, and will get a heatsink on the boat.

Still open:

1. **Module placement (needed for layout, not the schematic):** modules on the
   overhang's underside hang beside the Pi, which keeps the stack low. Their top
   faces then point down, so the NeoPixel and reset button may be hidden; the USB
   port can still face the board's outer edge. Modules on top are easier to see and
   reach, but make the stack taller. This depends on the space in the hull, and on
   whether the NeoPixel needs to be visible once installed.
2. **D1, the USB diode:** the Feather's USB pin is its USB port's 5 V line, so
   plugging in a laptop with the board powered ties the laptop's 5 V to U1's
   output. D1 prevents that, but costs about 0.3 V, leaving about 4.7 V. That
   should still charge the LiPo, but check it. The alternative is no diode and a
   rule never to plug in USB with the board powered.
3. **Reverse polarity:** D2 and F1 give basic protection, and a keyed J1 prevents
   most mistakes. U1 has no protection of its own, so add a reverse-protection FET
   if J1 will be connected and disconnected often.
4. **Ground return:** the ESC's signal ground joins the board's ground, so some
   motor return current could flow through the servo lead and the board if the ESC
   and J1 grounds meet far apart. Join them at one point, at the Victron's negative
   terminal, and keep the ESC's negative wire short and heavy.
5. **Cold-start glitch:** between power-on and `boot.py` driving GPIO11 low, EN
   is high, so the Pi's supply may start for a moment. Today's circuit does the
   same. Worth measuring at the Pi's 5 V before the design is final; a small
   capacitor on EN could delay the start if it's a problem.
6. **Lights and comms:** do the marker lights or satellite beacon need their own
   switched outputs now, or are the J7 spares enough for a first board?
7. **Battery temperature:** LiFePO4 must not be charged below about 0 °C, and
   nothing measures it yet. A thermistor input on SPARE_A1 would only add a
   resistor and a connector.
