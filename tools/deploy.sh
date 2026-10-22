#!/bin/bash
# Deploys a commit to the boat: checks it, pushes it to the Pi's checkout, and
# has the Pi apply it (services, and the RP2040 if its firmware changed).
# Usage: tools/deploy.sh [--flash | --no-flash] [--no-check] [REF]
#   REF defaults to HEAD. Set ROBOAT_HOST to deploy somewhere other than roboat1.
set -euo pipefail

host=${ROBOAT_HOST:-roboat1}
repo=roboat
flash=
check=1
ref=HEAD
while [ $# -gt 0 ]; do
    case $1 in
        --flash | --no-flash) flash=$1 ;;
        --no-check) check= ;;
        -h | --help) sed -n '2,5p' "$0"; exit 0 ;;
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

# The Pi's power must ride through the RP2040's reset (see Compute.md).
if [ "$(ssh "$host" cat /proc/sys/kernel/random/boot_id)" != "$boot_id" ]; then
    echo "The Pi rebooted during the deploy. An RP2040 reset should leave its power on;" >&2
    echo "check the Pi supply's EN wiring (Compute.md, power safety rules)." >&2
    exit 1
fi
