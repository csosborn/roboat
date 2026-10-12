# Roboat!

An autonomous, solar-powered boat. An RP2040 microcontroller handles power monitoring and control and supervises a Raspberry Pi, which provides data storage, navigation, planning, and communications.

## Design documents

- [Compute.md](Compute.md): compute architecture and the power-management state machine
- [PowerSystem.md](PowerSystem.md): battery, charge controller, and solar array selection
- [SolarArrayTrade.md](SolarArrayTrade.md): solar array trade study

## Repository layout

| Path | Contents |
| --- | --- |
| `src/micro/` | MicroPython code for the RP2040 Feather (power FSM, Victron MPPT, INA260, Pi link) |
| `src/pi/` | Raspberry Pi monitor service, TIG stack (Telegraf/InfluxDB/Grafana), and systemd units; see [setup notes](src/pi/TIG/setup.md) |
| `src/build-tools/` | Docker container for building custom MicroPython firmware |
| `printed_parts/` | STL files for 3D-printed parts |
| `take1/` | The original Arduino/Eagle-based attempt, kept for reference |
