# Deploy tools

Code reaches the boat only through git: commit on the laptop, then deploy that commit. Nothing is edited on the Pi or the RP2040 directly, so what's running is always an identifiable commit. The RP2040 reports its commit in every status message (the `rp2040_status` measurement in InfluxDB).

```bash
tools/deploy.sh            # deploy HEAD
tools/deploy.sh some-branch
tools/deploy.sh --no-flash # update the Pi but leave the RP2040 alone
tools/deploy.sh --flash    # reflash the RP2040 even if its files didn't change
```

**While the Pi's relay drops out during an RP2040 reset** (see the power safety rules in `Compute.md`), flash with `tools/deploy.sh --flash-halt` instead. The Pi shuts down cleanly, and the RP2040 resets a minute after flashing. The relay dropping out then power-cycles the halted Pi, which boots again. The script waits for the Pi to come back and for the RP2040 to report the new commit.

`deploy.sh` runs `check.sh` (host tests plus a MicroPython compile of every firmware file), pushes the commit to the Pi's `deployed` branch over SSH, and runs `pi_apply.sh` there. That script:

- installs any systemd unit that differs from the installed copy, and reloads systemd;
- updates the monitor's virtualenv if its requirements changed, and restarts the monitor if its code or unit changed;
- runs `docker-compose up` if the TIG stack's configuration changed;
- flashes the RP2040 with `rp2040_flash.py` if `src/micro` changed. It flashes over the serial link that carries telemetry (`/dev/ttyAMA3`), stopping the monitor for the duration: the firmware's `maintenance` command moves its REPL onto that link. If the board doesn't respond, for example because its firmware predates serial deploys, it falls back to USB.

The flash stages every changed file on the RP2040 and verifies it before replacing anything, then resets the board and waits for its boot status message to report the new commit. If it fails part way, the board's files are unchanged; the interrupted firmware resumes on its own within 15 minutes, or immediately with a reset.

## One-time Pi setup

The Pi's checkout at `~/roboat` must accept pushes to its checked-out branch, and refuse them if someone has edited files there:

```bash
git -C ~/roboat config receive.denyCurrentBranch updateInstead
git -C ~/roboat switch -c deployed
```

The secrets in `src/pi/TIG/*.env` stay on the Pi and are never deployed; see `src/pi/TIG/setup.md`.
