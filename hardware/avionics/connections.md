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
  apart from what it doesn't have yet: the rudder output, the stern board's
  temperature probe, and the BEC sense.
- Use the board itself to fix the wiring: a solid ground plane and a short, wide
  5 V path to the Pi.
- Leave open questions as headers and spare footprints, not decisions.
- Keep servo and ESC wiring in the stern: the ESC lead and rudder servo plug into
  a small stern board (`hardware/stern/`), linked to this one by a 6-pin cable
  (J10, see "Stern link" below).

## Parts

| Ref | Part | Mounting | Notes |
|---|---|---|---|
| A1 | Adafruit Feather RP2040 | Socketed | Pin numbers are from the `Adafruit-Feather-RP2040` KiCad symbol (github.com/bluepylons/Adafruit-RP2040-KiCAD, MIT). Its LiPo stays on its own JST connector. |
| U1 | Pololu D24V7F5 | Socketed | Always-on 5 V, 600 mA. Footprint `roboat:Pololu_D24V7F5`: VIN, GND, VOUT at 0.1 in. No reverse-voltage protection. |
| U2 | Pololu D36V28F5 | Socketed | Pi's 5 V. Footprint `roboat:Pololu_D36V28F5`: EN, VIN, GND, GND, VOUT in a row, PG 0.1 in above EN. Two M2 holes. |
| U3 | TI INA260AIPWR, TSSOP-16 | Soldered | Load-input current and voltage monitor, with its 2 mOhm shunt built in. Replaces v0.1's Adafruit breakout (A2) with the same circuit, minus the terminal block. A0 and A1 to GND give 0x40, as before. Footprint `Package_SO:TSSOP-16_4.4x5mm_P0.65mm`, no exposed pad. |
| Q1 | BSS138 | Soldered | Replaces the level shifter: it's the same circuit as the one channel in use. |
| Q2 | BSS138 | Soldered | Switches the drive relay's input from 5 V. |
| R1 | 10k | Soldered | Holds GPIO11 high during an RP2040 reset. Don't raise this value (see below). |
| R2, R3 | 10k, 15k | Soldered | PG divider, about 3.04 V at the pin. |
| R4, R5 | 10k, 15k | Soldered | Victron TX divider, about 3.06 V at the pin. |
| R6, R7 | 100k, 100k | Soldered | LiPo divider. `LIPO_CAL` needs rechecking with the real parts. |
| R8, R9 | 1k | Soldered | Series resistors on the Pi UART. |
| R10 | 100k | Soldered | Holds Q2 off whenever GPIO7 isn't driving it, including with the Feather out of its socket. |
| R11, R12 | 1k | Soldered | Series resistors on the ESC and rudder signals, at the source end of the stern link. |
| R13 | 220R, 1206 | Soldered | Feeds the stern board's temperature sensor from 5V_AON. Limits a short in the cable to about 23 mA (0.11 W, within a 1206's 0.25 W). |
| R14 | 4.7k | Soldered | 1-Wire pull-up to 3.3 V. |
| R15 | 1k | Soldered | Series resistor on the Victron's RX. Limits current from a 5 V pull-up inside the Victron into GPIO24's protection diode. |
| R16, R17 | 10k | Soldered | I2C1 pull-ups to 3.3 V, which the INA260 breakout used to provide. The GPS and IMU breakouts on J4 add their own 10k each. |
| R18, R19 | 10k | Soldered | I2C0 pull-ups to 3.3 V, so J5's bus works with a breakout that has none. |
| C1 | 0.1 uF | Soldered | At A0, as close to the socket pin as possible. |
| C3 | 0.1 uF | Soldered | At A1 (GPIO27), filtering BEC_SENSE after its trip down the cable. |
| C4 | 0.1 uF | Soldered | U3's supply decoupling, at `U3.10`. |
| C2 | 33 uF, 50 V electrolytic | Soldered | At U1's VIN. Pololu warns of destructive LC spikes on U1, whose limit is 36 V. |
| D1 | SS12 Schottky, 20 V 1 A, SMA | Soldered | See open question 2. About 0.3-0.4 V drop at the RP2040 side's 0.1-0.3 A. |
| D2 | SMBJ18A TVS | Soldered | Clamps spikes from the motor sharing the load output, to about 29 V against U1's 36 V limit. Reverse polarity makes it conduct and blow F1. |
| F1 | 3 A slow-blow (T3A) 5x20 mm cartridge fuse, e.g. Littelfuse 0218003.MXP | Two Keystone 3517 clips, through-hole | Covers the load input. Sized for the logic and Pi only, about 1 A. The ESC's feed never crosses the board. A low-breaking glass fuse is enough because the Victron's load output limits its own short-circuit current. Field-replaceable; spares are common. Footprint `Fuse:Fuseholder_Clip-5x20mm_Keystone_3517_Inline_P23.11x6.76mm_D1.70mm_Horizontal`. |
| J1 | Load input, 2 pins | Screw terminal or similar | From the Victron's load output, on its own wires. The ESC's relay taps the load output separately. 1 = +, 2 = GND. |
| J2 | Raspberry Pi header, pins 1-28, without pin 3 | 2x14 female, underside | The board stacks on the Pi's 40-pin header, covering pins 1-28 only, so the area over pins 29-40 is free for layout. Numbers are the Pi's physical pins. Mirrored in layout: see below. Pin 3's contact is pushed out of the socket: see below. Symbol `roboat:Pi_Header_2x14_NoPin3`, footprint `roboat:PinSocket_2x14_P2.54mm_Vertical_NoPin3`. v0.1 used a 2x20 socket. |
| J3 | VE.Direct, JST-PH 3 pins | S3B-PH-K (side entry) | 1 = GND, 2 = RX, 3 = TX. The cable leaves out the Victron's +5 V, which isn't needed. v0.1 had 4 pins, with pin 4 = +5 V unconnected. |
| J4 | STEMMA QT (JST SH 4) | SMD | I2C1, for the GPS and IMU. 1 = GND, 2 = 3.3 V, 3 = SDA, 4 = SCL. |
| J5 | STEMMA QT (JST SH 4) | SMD | I2C0, so the IMU can leave the shared bus without a new board. Same pinout as J4. |
| J7 | Spare GPIO header, 7 pins | 0.1 in | 1 = 3.3 V, 2 = GND, 3-7 = spare pins. Was 9 pins: GPIO25 and GPIO27 went to the stern link. |
| J9 | Drive relay input, 2 pins | 0.1 in or screw terminal | 1 = relay input +, 2 = relay input -. The relay itself stays off the board. |
| J10 | Stern link, JST-PH 6 pins | B6B-PH-K (vertical) or S6B-PH-K (side entry) | Replaces J6 (ESC) and J8 (rudder servo), which move to the stern board. Pinout under "Stern link". |

## Nets

Status: **Built** is on the boat now. **Changed** is on the boat but altered
here. **New** is not on the boat yet.

| Net | Connects | Status | Notes |
|---|---|---|---|
| LOAD_IN | `J1.1` `F1.1` | New | Fuse added. |
| LOAD_FUSED | `F1.2` `U3.1` `U3.2` `U3.3` `D2.K` | Changed | U3's three IN+ pins. |
| VBUS_12V | `U3.14` `U3.15` `U3.16` `U3.12` `U1.VIN` `U2.VIN` `C2.1` | Built | 12.0-14.2 V in normal use. C2 added. U3's three IN- pins, and its VBUS pin, so it measures the voltage after the shunt as the breakout's default VBUS jumper does. |
| GND | `J1.2` `U1.GND` `U2.GND1` `U2.GND2` `A1.4` `U3.6` `U3.11` `U3.4` `U3.5` `C4.2` `C1.2` `C2.2` `D2.A` `Q2.S` `R10.2` `R3.2` `R5.2` `R7.2` `J2.6` `J2.9` `J2.14` `J2.20` `J2.25` `J3.1` `J4.1` `J5.1` `J7.2` `J10.5` `C3.2` | Changed | One plane. The prototype lost 0.29 V here at 1.5 A. `U3.4` (A1) and `U3.5` (A0) set its address to 0x40. |
| 5V_AON | `U1.VOUT` `D1.A` `J9.1` `R13.1` | Changed | Also feeds the drive relay's input, about 15 mA at most, and the stern board's temperature sensor through R13. |
| FEATHER_USB | `D1.K` `A1.26` | Changed | Feather's USB pin. Was fed directly. |
| 5V_PI | `U2.VOUT` `J2.2` `J2.4` `R2.1` | Changed | Target: at least 4.9 V at the Pi at 1.5 A. |
| 3V3 | `A1.2` `A1.3` `R1.1` `Q1.G` `U3.10` `C4.1` `R16.1` `R17.1` `R18.1` `R19.1` `J4.2` `J5.2` `J7.1` `R14.1` | Built | From the Feather's regulator. Never sent down the stern link. |
| LIPO_BAT | `A1.28` `R6.1` | Built | |
| LIPO_SENSE | `R6.2` `R7.1` `C1.1` `A1.5` | Built | GPIO26. |
| PI_EN_CTRL | `A1.23` `R1.2` `Q1.S` | Changed | GPIO11. High or floating = Pi on; low = Pi off. Same as today. |
| PI_EN | `Q1.D` `U2.EN` | Changed | Keep this trace short: high impedance, with a precise threshold. |
| PI_PG | `U2.PG` `R2.2` `R3.1` `A1.22` | Built | GPIO10. |
| VE_TX | `J3.3` `R4.1` | Built | Idles at 5.1 V. Must never reach the Feather undivided. |
| VE_TX_3V3 | `R4.2` `R5.1` `A1.21` | Built | GPIO9, UART1 RX. |
| VE_RX_3V3 | `A1.9` `R15.1` | New | GPIO24, UART1 TX. Idles high; the firmware sends nothing yet. |
| VE_RX | `R15.2` `J3.2` | New | To the Victron's RX, for its HEX protocol. |
| PI_LINK_TX | `A1.15` `R8.1` | Changed | GPIO0, UART0 TX, 115200 baud. |
| PI_LINK_TX_R | `R8.2` `J2.21` | Changed | Pi GPIO9, RXD4 (`/dev/ttyAMA4`, see `src/pi/TIG/setup.md`). v0.1 used UART3, on pin 29. Not UART0 (pins 8 and 10): roboat1's GPIO15 input is damaged. |
| PI_LINK_RX | `A1.14` `R9.1` | Changed | GPIO1, UART0 RX. |
| PI_LINK_RX_R | `R9.2` `J2.24` | Changed | Pi GPIO8, TXD4. v0.1 used pin 7. Pins 21 and 24 are the Pi's SPI0, which stays off. |
| I2C1_SDA | `A1.17` `U3.8` `R16.2` `J4.3` | Built | GPIO2, 400 kHz. GPS 0x10, INA260 0x40, IMU 0x4A. |
| I2C1_SCL | `A1.18` `U3.9` `R17.2` `J4.4` | Built | GPIO3. |
| I2C0_SDA | `A1.24` `R18.2` `J5.3` | New | GPIO12. |
| I2C0_SCL | `A1.25` `R19.2` `J5.4` | New | GPIO13. |
| DRIVE_PWR_EN | `A1.19` `Q2.G` `R10.1` | Changed | GPIO7, high = ESC on. Same polarity as today. |
| DRIVE_RELAY_N | `Q2.D` `J9.2` | New | |
| DRIVE_PWM | `A1.20` `R11.1` | Changed | GPIO8, 50 Hz; 1.5 ms is neutral. |
| DRIVE_PWM_R | `R11.2` `J10.3` | Changed | To the ESC through the stern board. |
| RUDDER_PWM | `A1.16` `R12.1` | New | GPIO6. The pin is a proposal; the firmware has no rudder output yet. |
| RUDDER_PWM_R | `R12.2` `J10.4` | New | To the rudder servo through the stern board. |
| SENSOR_5V | `R13.2` `J10.1` | New | The stern board's temperature sensor supply. |
| ONEWIRE | `A1.10` `R14.2` `J10.2` | New | GPIO25. 1-Wire bus for the stern board's DS18B20 temperature probe. |
| BEC_SENSE | `A1.6` `C3.1` `J10.6` | New | GPIO27, ADC1. BEC_5V divided by 3 on the stern board, so 1.67 V for a 5 V BEC. |
| SPARE_A2 | `A1.7` `J7.3` | New | GPIO28, ADC. |
| SPARE_A3 | `A1.8` `J7.4` | New | GPIO29, ADC. |
| SPARE_SCK | `A1.11` `J7.5` | New | GPIO18. |
| SPARE_MOSI | `A1.12` `J7.6` | New | GPIO19. |
| SPARE_MISO | `A1.13` `J7.7` | New | GPIO20. |

Deliberately unconnected:

| Pin | Why |
|---|---|
| `A1.1` RESET | The Feather's own button is enough. A reset counts as a cold start, so it holds the Pi off. |
| `A1.27` ENABLE | Pulling it low would stop the Feather's 3.3 V regulator. |
| `U3.7` ALERT | Not used by the firmware. |
| `U3.13` NC | Not connected inside the chip. |
| `J2` pins 27 and 28 | Reserved for a HAT ID EEPROM, which this board doesn't have. |
| All other `J2` pins | The Pi's remaining GPIOs aren't used. Pins 29-40 have no socket at all. |

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
BEC, which will power the rudder servo on the stern board.

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
- BEC_5V never reaches this board: it runs from the ESC to the servo on the stern
  board, so servo current stays there, away from the Pi's supply and the sensors.
  This board sees only BEC_SENSE, divided down.
- R11 and R12 limit current into an unpowered ESC or servo. The firmware also
  drops the ESC signal whenever the relay goes off (branch `esc-signal-off`). The
  rudder output, when it's added, must do the same, and can also wait for
  BEC_SENSE to show the BEC is up.

## Stern link

J10 here and J1 on the stern board (`hardware/stern/connections.md`) carry the
same nets on the same pins. `tools/check_link.py` checks the two boards'
netlists against each other, pin by pin.

| Pin | Net | This board | Stern board |
|---|---|---|---|
| 1 | SENSOR_5V | 5V_AON through R13 | DS18B20 supply |
| 2 | ONEWIRE | GPIO25, R14 pull-up to 3.3 V | DS18B20 data |
| 3 | DRIVE_PWM_R | GPIO8 through R11 | ESC signal |
| 4 | RUDDER_PWM_R | GPIO6 through R12 | Rudder servo signal |
| 5 | GND | Ground plane | Ground: signal and sensor returns only |
| 6 | BEC_SENSE | GPIO27 (ADC), C3 | BEC_5V divided by 3 |

- **Cable:** a JST-PH 6-way cable with a housing at each end, wired pin 1 to pin
  1. Check a bought cable end to end before use: some are made reversed.
- **Order:** SENSOR_5V sits next to ONEWIRE, as on the probe itself, and away from
  BEC_SENSE, with GND between BEC_SENSE and the PWM signals.
- **No supply crosses the link apart from SENSOR_5V,** which R13 limits. The servo's
  current, BEC_5V and the Feather's 3.3 V all stay off the cable.
- **Shorts:** a short from SENSOR_5V to ONEWIRE puts at most about 5 mA, through
  R13, into GPIO25's protection diode. BEC_SENSE stays under 2.5 V even with a
  7.4 V BEC setting.
- **Length:** 50 Hz PWM and 1-Wire with a 4.7k pull-up are both fine over a few
  metres. If a long cable makes the 1-Wire bus unreliable, lower R14 to 2.2k.

## Stacking on the Pi

The board sits on the Pi's 40-pin header, covering most of the Pi, and overhangs
on the side away from the USB and Ethernet ports. `tools/add_pi4_outline.py` draws
the Pi beneath it, from Raspberry Pi's mechanical drawing (RP-008342-DS), as one
group that moves together.

- **Height:** the usual 8.5 mm socket puts the board's underside about 11 mm above
  the Pi. The USB and Ethernet ports stand taller than that, so the board stays
  clear of them.
- **CPU cutout:** the board has a cutout above the CPU, so a heatsink can come up
  through it.
- **WiFi antenna:** the Pi's antenna is the strip between its pin 1 corner and its
  WiFi can. A keepout on both copper layers, part of the Pi group, keeps tracks,
  vias, pads and pours off the board above it, including the overhang beside it.
  The position is inferred from the parts around the antenna; check it on a real Pi.
- **No pin 3:** the inner row (pins 1, 3, 5) stands between U2 and the 5 V pins 2
  and 4, and its pads leave no room for a track. Pin 3 is the Pi's GPIO2 (I2C1 SDA,
  with a 1.8 kOhm pull-up on the Pi), unused here, so J2 has no copper there and
  5V_PI runs through the gap. **Push pin 3's contact right out of the socket before
  fitting it**, rather than clipping its tail: a contact left in place would touch
  the Pi's GPIO2 just above 5 V copper under only solder mask. This gives up the
  Pi's I2C1; its other I2C buses can be enabled on other pins if ever needed.
- **Support:** the header can't carry the board on a boat. Use standoffs at the
  Pi's four mounting holes (H1-H4, M2.5), and add holes at the far corners of any
  overhang, fixed to the same base as the Pi.
- **GPS and IMU on standoffs:** H5-H9, unplated 2.5 mm holes for M2 hardware. The
  GPS sits on H5 and H6, along the edge beyond the Pi's header. The IMU sits on
  H7, H8 and H9, three of its four corners, so it can't rock. The breakouts mount
  above the board on nylon standoffs, which keep steel away from the IMU's
  magnetometer, and connect to J4/J5 by STEMMA QT cables. The GPS needs a clear
  view of the sky.
- **IMU axes:** the silkscreen beside the IMU marks +X and +Y, with Z out of the
  board's top face (a right-handed set). The firmware's mapping from the IMU's
  frame to the boat's should be checked against these once the board is fitted.
- **J2 is on the underside:** a socket on the back of the board mirrors the pin
  order compared with the Pi's top view. Check it on a 1:1 print against a real
  Pi before ordering.
- **Pins 29-40 stand bare:** J2 covers only pins 1-28. The Pi's other twelve pins
  stand uncovered under the board, their tips about 2.5 mm below its underside
  with an 8.5 mm socket. They carry live GPIOs and ground, so keep the underside
  over them free of exposed copper and parts.
- **No fuse on the Pi side:** power through the 40-pin header bypasses the Pi's own
  input protection, so U2 and F1 are all that's guarding it.

## Layout requirements

Each of these comes from a fault on the prototype.

- **Ground:** a solid plane, with nothing routed through it between J1, U2 and
  J2.
- **Pi 5 V:** a short, wide pour from U2 to J2. Allow under 20 milliohms each
  way, about 30 mV at 1.5 A. Tie in all five of J2's ground pins (6, 9, 14, 20, 25).
- **C1:** right at `A1.5`. On the prototype it sits about six inches of jumper
  away.
- **Victron divider:** R4 and R5 next to the Feather, so only the divided signal
  crosses the board near it. R15 beside them.
- **U2's EN:** Q1 next to U2.
- **J10:** at the board edge nearest the stern, with R11, R12, R13 and C3 close to
  it.
- **D2 and C2:** close to J1 and U1, with short connections to the plane.
- **U3:** pours to its IN+ (pins 1-3) and IN- (pins 14-16) groups; the shunt is
  inside the chip, so no Kelvin routing is needed. C4 right at pin 10.
- **Test points:** VBUS_12V, 5V_AON, 5V_PI, 3V3, PI_EN, PI_PG and GND, each
  reachable with the Pi and modules fitted.

## Open questions

Settled on 2026-11-06:

- The board stacks on the 40-pin header, and may overhang the Pi.
- The INA260 is socketed. Changed for v0.2 (2026-11-16): the chip goes on the
  board as U3, because the breakout takes too much room.
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
   output. D1 (an SS12) prevents that, but costs about 0.3-0.4 V, leaving about 4.6-4.7 V. That
   should still charge the LiPo, but check it. The alternative is no diode and a
   rule never to plug in USB with the board powered.
3. **Reverse polarity:** D2 and F1 give basic protection, and a keyed J1 prevents
   most mistakes. U1 has no protection of its own, so add a reverse-protection FET
   if J1 will be connected and disconnected often.
4. **Ground return:** the ESC's signal ground joins the board's ground through the
   stern link, so some motor return current could flow through the link and the
   board if the ESC and J1 grounds meet far apart. Join them at one point, at the
   Victron's negative terminal, and keep the ESC's negative wire short and heavy.
5. **Cold-start glitch:** between power-on and `boot.py` driving GPIO11 low, EN
   is high, so the Pi's supply may start for a moment. Today's circuit does the
   same. Worth measuring at the Pi's 5 V before the design is final; a small
   capacitor on EN could delay the start if it's a problem.
6. **Lights and comms:** do the marker lights or satellite beacon need their own
   switched outputs now, or are J7's five remaining spares enough for a first board?
7. **Battery temperature:** LiFePO4 must not be charged below about 0 °C, and
   nothing measures it yet. SPARE_A1 went to BEC_SENSE, but DS18B20s share a
   1-Wire bus, so a second probe on ONEWIRE could measure the battery: it would
   need only a 3-pin header here (SENSOR_5V, ONEWIRE, GND).
8. **Victron RX levels:** the Victron's TX idles at 5.1 V, so it's a 5 V device,
   and Victron doesn't promise that its RX accepts 3.3 V logic, though many 3.3 V
   boards drive it directly. Check that the MPPT answers a HEX ping. If it
   doesn't, a level shifter is the fix; R15 keeps the attempt harmless.
   Writing settings can restart the MPPT and drop the load output (it did during
   the 2026-10-11 low-battery test), so the firmware should read freely but write
   rarely, and never in a way that can leave the load output off.
