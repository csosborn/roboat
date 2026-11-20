# Battery characterization, October 2026

What one full discharge and recharge of the boat's battery taught us, and what
it means for the firmware. This is a single cycle at light loads and an
unmeasured room temperature. Read the numbers as a first calibration, not a
datasheet.

## Summary

- **Usable capacity is about 18.8 Ah** from full to the Victron's 12.0 V load
  cut-off, at 0.1-0.4 A. That's 94% of the 20 Ah rating. Recharging from the
  cut-off to full took **18.65 Ah**, which agrees within 1%.
- **The Victron's battery current is good enough to count charge with**, over
  days. Charge counting, not voltage, should be the basis of any state-of-charge
  estimate.
- **Voltage says almost nothing about charge between about 90% and 15%.** On
  discharge the curve is nearly flat, at 1-15 mV per Ah over most of that
  range. On charge it sits 0.3-0.4 V higher than on discharge, at the same
  state of charge.
- **Three reliable landmarks:**
  - **Full:** 14.1 V or more with a charge current below 0.5 A.
  - **A mid-cycle step at about 57%:** a step of about 0.1 V that appears at
    the same state of charge in both directions.
  - **The final knee, below about 12.7 V:** the voltage falls faster and
    faster, reaching more than 1 V per Ah just before 12.0 V.
- **The Pi's 12.8 V shutdown leaves about 2.5 Ah (13%).** That's about 20 hours
  of the RP2040, GPS and sensors on their own at today's 1.4 W.

## Setup

| | |
|---|---|
| Battery | 12 V 20 Ah LiFePO4 |
| Charger | Victron MPPT: absorption 14.2 V, float 13.5 V. The load output (feeding the DC-DC converter for the Pi and RP2040) is off below 12.0 V and on above 13.2 V. |
| Charge source | A bench supply standing in for the solar panel, giving about 54 W (about 3.6 A of charge). |
| Load, Pi on | 0.35-0.4 A from the battery (about 4.5 W) |
| Load, Pi off | 0.12 A (about 1.4 W: the RP2040, GPS and INA260, plus converter losses) |
| Measurement | The Victron's battery voltage and current (`V`, `I` over VE.Direct, 10 mA resolution), and the INA260 on the load side of the Victron's load output. One-minute means. |
| Temperature | Indoors; not measured |

## Timeline

All times are PDT.

| When | What |
|---|---|
| 10-11 10:00 | Full: absorption at 14.2 V, with the tail current down to 0.3 A. Charging then stopped. |
| 10-11 to 10-13 | Discharge with the Pi on, at 0.35 A. |
| 10-13 12:38 | The battery had been below 12.8 V for 2 minutes, so the RP2040 shut the Pi down cleanly. |
| 10-13 12:39 to 17:11 | **No data.** The RP2040's flash log overflowed before the Pi came back (fixed in PR #10). The charge count bridges this gap at 0.12 A. |
| 10-14 06:56 | Charging resumed for about 1.2 Ah. The battery got down to 12.44 V before this. |
| 10-14 08:14 | Charging off. The Pi shut down again at 12.8 V. |
| 10-14 20:38 | The Victron's load output turned off at 12.02 V. The RP2040 carried on, on its LiPo. |
| 10-14 21:58 | Charging on: bulk at about 3.6 A. |
| 10-15 02:50 | Absorption at 14.2 V. |
| 10-15 03:20 | The tail current fell below 0.1 A: full again. |
| 10-15 04:45 | The charger dropped to float. |

## Discharge curve

"Used" is counted from full. "SoC" is the state of charge, as a percentage of the measured 18.8 Ah. "Slope" is the voltage change per Ah drawn since the previous row.

| Time | Battery V | Current | Used | SoC | Slope |
|---|---|---|---|---|---|
| 10-11 18:00 | 13.24 | 0.48 A | 1.7 Ah | 91% | |
| 10-12 03:00 | 13.23 | 0.35 A | 4.4 Ah | 77% | 3 mV/Ah |
| 10-12 09:00 | 13.20 | 0.37 A | 6.4 Ah | 66% | 15 mV/Ah |
| 10-12 12:00 | 13.16 | 0.36 A | 7.5 Ah | 60% | 38 mV/Ah (step) |
| 10-12 15:00 | 13.09 | 0.36 A | 8.5 Ah | 55% | 66 mV/Ah (step) |
| 10-12 21:00 | 13.05 | 0.37 A | 10.7 Ah | 43% | 18 mV/Ah |
| 10-13 03:00 | 13.03 | 0.34 A | 12.9 Ah | 32% | 8 mV/Ah |
| 10-13 06:00 | 12.99 | 0.35 A | 13.9 Ah | 26% | 39 mV/Ah |
| 10-13 09:00 | 12.90 | 0.41 A | 15.0 Ah | 20% | 82 mV/Ah |
| 10-13 12:38 | 12.80 | 0.37 A | 16.3 Ah | 13% | 67 mV/Ah (Pi shutdown) |
| 10-13 18:00 | 12.78 | 0.12 A | 17.0 Ah | 10% | |
| 10-14 00:00 | 12.70 | 0.12 A | 17.7 Ah | 6% | 110 mV/Ah |
| 10-14 03:00 | 12.67 | 0.12 A | 18.0 Ah | 4% | 83 mV/Ah |
| 10-14 06:00 | 12.53 | 0.12 A | 18.4 Ah | 2% | 389 mV/Ah |
| 10-14 18:00 | 12.39 | 0.12 A | 18.5 Ah | 2% | 900 mV/Ah* |
| 10-14 20:00 | 12.12 | 0.12 A | 18.7 Ah | 0.4% | 1250 mV/Ah* |
| 10-14 20:38 | 12.02 | 0.12 A | 18.8 Ah | 0% | Load output off |

The rows from 10-14 18:00 on come from the second discharge, after the
partial recharge, placed by their net charge. Their slopes (*) are over the
preceding hour of that discharge.

Some details:

- **Current matters, but not much at these loads.** When the Pi shut down on
  10-14, the current fell from 0.36 A to 0.12 A, and the voltage rose 35 mV:
  about 0.15 Ω, wiring included. The motor will draw far more, and pull the
  voltage down much further.
- **The steepening that starts at 13.0 V (about 30%) is gradual:** 40-110 mV
  per Ah over the next 4 Ah. The sharp final knee starts at about 12.67 V,
  with under 1 Ah left.

## Charge curve

From the 12.0 V cut-off, at a steady 3.6 A:

| Time | Battery V | Charged in | SoC |
|---|---|---|---|
| 10-14 22:00 | 13.01 | 0.7 Ah | 4% |
| 10-14 23:00 | 13.41 | 4.4 Ah | 23% |
| 10-15 00:20 | 13.48 | 9.2 Ah | 49% |
| 10-15 01:10 | 13.59 | 12.2 Ah | 65% |
| 10-15 02:00 | 13.63 | 15.2 Ah | 82% |
| 10-15 02:40 | 13.89 | 17.7 Ah | 95% |
| 10-15 02:50 | 14.19 | 18.2 Ah | 98% |
| 10-15 03:10 | 14.20 | 18.58 Ah | |
| 10-15 03:20 | 14.19 | 18.62 Ah | 100% |

The rows from 02:50 are absorption at 14.2 V. The current was 0.41 A at 03:10,
and 0.11 A at 03:20.

The charge step (+0.11 V between 9.2 and 12.2 Ah in) is centred at 10.7 Ah,
about 57%. The discharge step is centred at about 7.9 Ah used, i.e. about
10.9 Ah (58%) remaining. These are the same feature: the transition between
LiFePO4's two voltage plateaus.

## What this means for the firmware

The thresholds below are as of PRs #9-#11.

- **The Pi shutdown at 12.8 V (sustained for 2 minutes)** happens at about 13%,
  under the Pi's 0.35 A load. The firmware comment says "15-20%", which is a
  little optimistic. The reserve it leaves, about 2.5 Ah, runs the RP2040 side
  for about 20 hours at 1.4 W. That's enough for a long night, but not a night
  plus a dark morning. Reducing the RP2040 side's draw makes the most
  difference here.
- **The main-power hysteresis at 12.4 V (down) and 12.6 V (up)** sits deep in
  the final knee. Below 12.4 V there was about 0.3 Ah, 2.6 hours at 0.12 A,
  before the Victron cut the load.
- **The Pi restart, at 13.0 V or more with over 10 W of solar,** is mostly a
  test that the sun is out. Under charge the battery passes 13.0 V almost
  immediately, even when nearly empty: 13.0 V came at 0.7 Ah in. The load
  output's 13.2 V reconnect came at 2.1 Ah in (11%). PR #11 makes the RP2040
  wait for the load output itself.
- **A battery model should count charge and use voltage only at the
  landmarks:**
  - Count the Victron's battery current. Over this cycle, charge counting
    stayed within about 1% of the truth.
  - Reset to 100% on 14.1 V or more with a charge current under 0.5 A.
  - Correct the estimate at the 57% step when it shows up, which needs a
    steady current and a slope check.
  - Correct it in the final knee, where the voltage-to-charge mapping is
    steep enough to be useful.
  - Learn the capacity from each full-to-knee discharge, and save the state to
    flash so it survives a reset.
  - Base the Pi shutdown on the estimated charge, with 12.8 V kept as a
    backstop.

## November 2026: more cycles, and the firmware's model

InfluxDB turned out to hold much more than this one cycle:
- about ten bench cycles from November 2025 to March 2026 (charged to 14.2 V
  at ~58 W, then discharged at ~0.43 A down to about 12.5 V);
- partial cycles from May to September 2026;
- about five cycles since October 2026, including a full run-down on
  2026-11-11 to 16 (`run-down-2026-11.csv`) that went past the cut-off to
  11.3 V.

What they add:

- **The charge counts agree across a year, so there's no measurable fade.**
  Recharges took 17.4-17.9 Ah from about 12.5 V in 2025-26, 18.5 Ah from
  12.03 V in October 2026, and 18.7 Ah from 11.31 V in November.
- **The discharge counts don't agree, and the low-current readings are why:**
  - In November the Victron read 0.00 A for hours while the INA260 measured
    ~30 mA flowing.
  - In 2025 it read ~0.1 A more than the INA260 (0.45 A against 0.345 A).
  - Its load current (`IL`) has 0.1 A steps, so it reads zero at the Pi-off
    load.
- **The Victron's current offset drifts.** Hourly means with the Pi on
  (October to November) put it anywhere from 38 mA below to 25 mA above the
  INA260, varying from day to day and by ~20 mA from hour to hour. It can't
  resolve a draw of a few mA.
- **About 22 mA leaves the battery that neither sensor sees.** Metered on
  2026-11-19, with the Pi off:
  - In the load-output lead, the meter matched the INA260 within ~2 mA at
    four readings, so nothing on the load output escapes the INA260.
  - In the MPPT's battery lead it read ~51 mA against the INA260's ~29 mA:
    the MPPT itself uses ~21 mA, and its own battery current leaves that out
    (it read 0.03 A, the load alone).
  - The Smart Battery Sense draws ~0.7 mA (4 mA while VictronConnect is
    connected to it).
  - It also explains the battery falling from 12.0 V to 11.3 V in 14 hours
    with the load output off on 11-16.
- **The Victron reads ~5% low while charging.** Counting discharge as the
  INA260 plus 22 mA, both run-downs come out ~1.0 Ah more than the Victron
  counted going back in (October 19.5 out, 18.5 in; November 18.8 out,
  17.8 in). A meter in the battery lead read ~1.8 A while the Victron said
  1.71-1.73 A. So the charge counts above are probably all ~5% low too
  (still no fade).
- **On that basis, full to the 12.0 V cut-off is about 19 Ah** at the Pi's
  loads: 18.8 Ah in November, 19.7 in October (with its 4.5-hour gap
  bridged). The Pi's 12.8 V shutdown came at about 2.2 Ah left (12%).
- **The battery's effective resistance is about 0.2 ohm.** The instant step
  when the Pi switches is ~0.1 ohm; the rest is relaxation over minutes. With
  0.2 ohm, the Pi-on (0.28 A) and Pi-off (0.03 A) discharge curves line up,
  and so does October's run at 0.12-0.41 A.
- **The firmware's old `BatteryModel` was often far off:**
  - It re-guessed SoC from voltage at every boot (11 boots in the week to
    11-17), using curves well off the measured ones. After the 11-14 boot it
    read ~80% all the way down to the cut-off, where the truth was 0-18%.
  - It also went to 100% at the start of bulk charging.

`src/micro/soc_model.py` replaces it, along the lines recommended above:
- It counts discharge from the INA260 plus the hidden 22 mA, and uses the
  Victron only when it reads at least 0.1 A more (the motor). Charging comes
  from the Victron, scaled up 5%.
- Full: 14.1 V or more with under 0.5 A going in, held for 2 minutes, or the
  Victron in float.
- It corrects with voltage only at a steady, light discharge at least 2 hours
  after charging, compensated at 0.2 ohm:
  - in the knee, below ~13.06 V, as a measurement;
  - on the plateaus, only as bounds: the upper plateau means at least
    11.8 Ah left, the lower one at most 11.0 Ah.
- It learns capacity from each stretch between full and the knee, in either
  direction.
- It saves its state to flash every 10 minutes. After a reset it picks up
  from the save, and charges the downtime once the GPS gives the time. It
  doesn't save again until then, so a second reset comes back to the same
  timed save.

It reports the charge left to the 12.0 V cut-off with a standard deviation
(InfluxDB `battery`: `cap_ah`, `soc`, `soc_sd_ah`, `full_ah`, and `basis`,
meaning what last set the estimate). Replaying both run-downs, it:
- reads 0% at the cut-off;
- learns 18.9-19.0 Ah each time;
- is unaffected by a reset;
- when started with no saved state, locks on as soon as the knee appears.

The Pi's shutdown and restart thresholds are unchanged. They should move to
the estimate only once it has proved itself on the boat.

## Limits of this data

- **One cycle, at light loads (0.1-0.4 A), indoors.** Capacity drops with cold
  and with high current. LiFePO4 must not be charged below about 0 °C, and
  nothing on the boat measures battery temperature yet.
- **The Victron reports current in 10 mA steps,** at very low currents it can
  read zero, and its offset drifts (see November 2026, above). The hidden
  22 mA and the 5% charging error each rest on a few eyeballed meter readings
  and two cycles.
- **All charging so far is from a bench supply** that runs to absorption
  every time. On real sun the battery may rarely reach full, so the count
  will run longer between resets to 100%.
- **The 4.5-hour gap on 10-13 is bridged** at the current that followed it
  (0.12 A, Pi off). That's right for that period, but not measured.
- **Rows recorded while the Pi was off** are means of 30-60 s snapshots, not of
  continuous readings.

## Tests still worth doing

- A discharge at motor-level current, to see how far the voltage sags under
  load and where 12.8 V then falls.
- A day or more on real sun, with variable current and partial charges. This is
  the case the battery model has to handle.
- Battery temperature, so later cycles can be compared fairly. The Smart
  Battery Sense measures it and the MPPT passes it on over VE.Direct HEX
  (register 0xEDEC); from 2026-11-20 it's in InfluxDB as `mppt.batt_temp_c`.
- Repeated full cycles, to see capacity fade. The battery model can record the
  capacity at each one.

## Reproducing

```bash
docs/battery/export.sh 2026-10-11T16:00:00Z 2026-10-15T16:00:00Z > docs/battery/discharge-2026-10.csv
python3 docs/battery/analyze.py docs/battery/discharge-2026-10.csv --from "10-11 10:30" --to "10-14 06:50" --every 180
python3 docs/battery/analyze.py docs/battery/discharge-2026-10.csv --from "10-14 21:50" --to "10-15 03:40" --every 10
```

Replaying telemetry through the firmware's model (with `--reset "MM-DD HH:MM"`
to simulate a restart):

```bash
python3 docs/battery/replay.py docs/battery/run-down-2026-11.csv --every 240
```

`export.sh` needs ssh access to `roboat1`, and reads the InfluxDB token there.
`analyze.py` counts charge from `--from` onward, so start each span at a known
reference point, such as full.

The columns of `discharge-2026-10.csv`, one row per minute:

| Column | Meaning |
|---|---|
| `time_utc` | Time, UTC |
| `batt_v` | Battery voltage (Victron) |
| `batt_i` | Battery current (Victron; positive is charging) |
| `load_i` | Load output current (Victron) |
| `solar_w` | Panel power (Victron) |
| `load_on` | Load output state (Victron; 1 is on). Recorded from 10-11 18:00. |
| `tracker_mode` | Charger state (Victron: 0 off, 1 limited, 2 tracking) |
| `load_bus_v` | Load-side voltage (INA260) |
| `logic_w` | Power drawn by everything on the load output (INA260) |
