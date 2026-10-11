#!/bin/bash
# Applies a deployed commit on the Pi. tools/deploy.sh runs this after pushing.
# Usage: tools/pi_apply.sh OLD_COMMIT NEW_COMMIT [--flash | --flash-halt | --no-flash]
#   --flash       flash the RP2040 even if its files didn't change
#   --flash-halt  flash the RP2040, then shut the Pi down before the RP2040
#                 resets. Needed while the Pi's relay drops out during an
#                 RP2040 reset: the reset then power-cycles a halted Pi
#                 instead of cutting a running one.
#   --no-flash    skip the RP2040 even if its files changed
set -euo pipefail
cd "$(dirname "$0")/.."

PI_LINK_PORT=/dev/ttyAMA3

old=$1
new=$2
flash=${3:-}

changed() {
    ! git diff --quiet "$old" "$new" -- "$@"
}

# systemd units: install any that differ from what's installed, whatever the
# reason (this also catches hand edits on the Pi).
installed_units=()
for unit in src/pi/etc/systemd/system/*.service; do
    dest=/etc/systemd/system/$(basename "$unit")
    if ! cmp -s "$unit" "$dest"; then
        sudo install -m 644 "$unit" "$dest"
        installed_units+=("$(basename "$unit" .service)")
    fi
done
if [ ${#installed_units[@]} -gt 0 ]; then
    echo "Installed systemd units: ${installed_units[*]}"
    sudo systemctl daemon-reload
fi

# Monitor
venv=src/pi/monitor/monitor.venv
if [ ! -x "$venv/bin/python" ]; then
    python3 -m venv "$venv"
    "$venv/bin/pip" install -q -r src/pi/monitor/requirements.txt
elif changed src/pi/monitor/requirements.txt; then
    "$venv/bin/pip" install -q -r src/pi/monitor/requirements.txt
fi
if changed src/pi/monitor || [[ " ${installed_units[*]} " == *" roboat-monitor "* ]]; then
    echo "Restarting roboat-monitor"
    sudo systemctl restart roboat-monitor
fi

# TIG stack: compose only recreates containers whose configuration changed.
if changed src/pi/TIG; then
    echo "Updating the TIG stack"
    (cd src/pi/TIG && docker-compose --profile interactive up --detach)
fi

# RP2040
if [ "$flash" != --no-flash ] && { [ "$flash" = --flash ] || [ "$flash" = --flash-halt ] || changed src/micro; }; then
    tools_venv=tools/.venv
    if [ ! -x "$tools_venv/bin/python" ]; then
        python3 -m venv "$tools_venv"
        "$tools_venv/bin/pip" install -q -r tools/requirements-pi.txt
    fi
    flash_args=(--version "$(git rev-parse --short=12 "$new")")
    [ "$flash" = --flash-halt ] && flash_args+=(--reset-delay 60)
    echo "Flashing the RP2040 over the serial link"
    status=0
    "$tools_venv/bin/python" tools/rp2040_flash.py "${flash_args[@]}" --serial "$PI_LINK_PORT" || status=$?
    if [ $status -ne 0 ] && [ $status -ne 3 ]; then
        # Firmware older than the serial deploy support ignores the request.
        echo "Serial flash failed; trying USB"
        "$tools_venv/bin/python" tools/rp2040_flash.py "${flash_args[@]}"
    elif [ $status -eq 3 ]; then
        exit 3
    fi
    if [ "$flash" = --flash-halt ]; then
        echo "Shutting the Pi down; the RP2040's reset should power it back up."
        sudo systemd-run --quiet --on-active=3 /usr/bin/systemctl poweroff
    fi
elif changed src/micro; then
    echo "RP2040 files changed but --no-flash was given; the board is still running the old firmware."
fi

echo "Deployed $(git log -1 --format='%h %s' "$new")"
