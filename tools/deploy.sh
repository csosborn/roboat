#!/bin/bash
# Deploys a commit to the boat: checks it, pushes it to the Pi's checkout, and
# has the Pi apply it (services, and the RP2040 if its firmware changed).
# Usage: tools/deploy.sh [--flash | --flash-halt | --no-flash] [--no-check] [REF]
#   REF defaults to HEAD. Set ROBOAT_HOST to deploy somewhere other than roboat1.
#   --flash-halt shuts the Pi down around the RP2040 reset (see pi_apply.sh)
#   and waits for both to come back running the new commit.
set -euo pipefail

host=${ROBOAT_HOST:-roboat1}
repo=roboat
flash=
check=1
ref=HEAD
while [ $# -gt 0 ]; do
    case $1 in
        --flash | --flash-halt | --no-flash) flash=$1 ;;
        --no-check) check= ;;
        -h | --help) sed -n '2,7p' "$0"; exit 0 ;;
        -*) echo "Unknown option $1" >&2; exit 2 ;;
        *) ref=$1 ;;
    esac
    shift
done

cd "$(git rev-parse --show-toplevel)"
sha=$(git rev-parse --verify "$ref^{commit}")

if [ -n "$check" ]; then
    if [ "$sha" != "$(git rev-parse HEAD)" ] || [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        echo "The checks run on the working tree, so they need a clean checkout of $ref." >&2
        echo "Commit or stash your changes, check out $ref, or pass --no-check." >&2
        exit 1
    fi
    tools/check.sh
fi

old=$(ssh "$host" "git -C $repo rev-parse HEAD")
boot_id=$(ssh "$host" cat /proc/sys/kernel/random/boot_id)
echo "Deploying $(git log -1 --format='%h %s' "$sha") to $host (was ${old:0:12})"
git push --force "$host:$repo" "$sha:refs/heads/deployed"
ssh "$host" "$repo/tools/pi_apply.sh $old $sha $flash"

if [ "$flash" = --flash-halt ]; then
    echo "Waiting for the Pi to come back..."
    deadline=$((SECONDS + 420))
    until id=$(ssh -o ConnectTimeout=5 "$host" cat /proc/sys/kernel/random/boot_id 2>/dev/null) \
            && [ "$id" != "$boot_id" ]; do
        if [ $SECONDS -ge $deadline ]; then
            echo "The Pi didn't come back within 7 minutes. If its red LED is lit, the relay held" >&2
            echo "through the RP2040's reset, so nothing power-cycled the halted Pi. Press the" >&2
            echo "RP2040's reset button: a cold start switches the relay off, then on again." >&2
            exit 1
        fi
        sleep 5
    done
    echo "The Pi is back (the RP2040's reset power-cycled it). Waiting for an RP2040 status message..."
    version=${sha:0:12}
    deadline=$((SECONDS + 180))
    until line=$(ssh "$host" "journalctl -u roboat-monitor -b --no-pager -o cat" \
            | grep "'src': 'status'" | grep "'version': '$version'" | tail -1) && [ -n "$line" ]; do
        if [ $SECONDS -ge $deadline ]; then
            echo "No RP2040 status message reporting version $version within 3 minutes." >&2
            exit 1
        fi
        sleep 10
    done
    echo "RP2040 is running $version: $line"
fi
