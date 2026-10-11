#!/bin/bash
# Runs the RP2040 firmware's host tests and compiles every firmware file with
# MicroPython's own compiler, which rejects some syntax CPython accepts.
set -euo pipefail
cd "$(dirname "$0")/.."

venv=tools/.venv
if [ ! -x "$venv/bin/python" ]; then
    python3 -m venv "$venv"
    "$venv/bin/pip" install -q -r tools/requirements-dev.txt
fi

"$venv/bin/python" -m pytest -q tests

failed=0
while IFS= read -r f; do
    if ! out=$("$venv/bin/python" -m mpy_cross -o /dev/null "$f" 2>&1); then
        echo "mpy-cross rejected $f: $out" >&2
        failed=1
    fi
done < <(find src/micro -name '*.py' -not -name 'version.py')
[ $failed -eq 0 ] && echo "All firmware files compile for MicroPython."
exit $failed
