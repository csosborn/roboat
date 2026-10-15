#!/usr/bin/env python3
"""Flash the RP2040's MicroPython files from this checkout.

Runs on the Pi, which reaches the RP2040 over USB or, with --serial, over the
serial link that also carries telemetry.

1. Interrupt the running firmware and enter the raw REPL. Over serial, this
   means stopping the monitor (which owns the port) and sending the firmware
   a maintenance command, which moves its REPL onto the link. Either way the
   firmware's watchdog is held off for 15 minutes and then resets the board,
   so an abandoned flash recovers itself.
2. Write every changed file as <name>.new and check its SHA-256 on the board.
3. Only once every file has verified: move the new files into place, delete
   files a previous deploy shipped that are no longer part of the firmware,
   record the manifest, and reset the board.
4. Wait for the new firmware's boot status message in the monitor's journal.
   With --reset-delay, the reset is instead left to run on the board after a
   delay, so the Pi can shut down first (see pi_apply.sh --flash-halt).

If anything fails before step 3, the files on the board are unchanged.
"""
import argparse
import ast
import binascii
import glob
import hashlib
import os
import subprocess
import sys
import time

import serial

MICRO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'micro')
# Linux (the Pi), then macOS.
PORT_GLOBS = ['/dev/serial/by-id/usb-MicroPython_*', '/dev/cu.usbmodem*']
NOT_SHIPPED = {'install.sh', 'notes.md', 'version.py'}
MANIFEST = 'deploy_manifest'
# Runtime state the firmware keeps on flash. A deploy never deletes these.
STATE_FILES = {'bootcount', 'pi_power', 'crash.log', 'crash.log.1', 'nowdt', MANIFEST}
# Left on the board by work that predates the manifest.
LEGACY_FILES = ['statemachine.py', 'relay_test.txt', 'relay_test2.txt', 'relay_test3.txt']
CHUNK = 768
BOOT_WAIT_S = 45
# Exit status when the files were installed but the new firmware wasn't seen
# booting; retrying the flash wouldn't help.
BOOT_CHECK_FAILED = 3
MAINTENANCE_COMMAND = b'\n{"cmd": "maintenance"}\n'

DEVICE_HELPERS = r"""
import os, binascii, hashlib
def _mkdirs(p):
    d = ''
    for part in p.split('/')[:-1]:
        d = d + '/' + part if d else part
        try:
            os.mkdir(d)
        except OSError:
            pass
def _hash(p):
    try:
        f = open(p, 'rb')
    except OSError:
        return None
    h = hashlib.sha256()
    while True:
        b = f.read(512)
        if not b:
            break
        h.update(b)
    f.close()
    return binascii.hexlify(h.digest()).decode()
def _manifest():
    try:
        with open('deploy_manifest') as f:
            return [l.strip() for l in f if l.strip()]
    except OSError:
        return None
"""


class DeviceError(Exception):
    pass


class RawRepl:
    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.1)

    def close(self):
        self.ser.close()

    def _read_until(self, marker, timeout):
        buf = b''
        deadline = time.monotonic() + timeout
        while not buf.endswith(marker):
            if time.monotonic() > deadline:
                raise TimeoutError('waiting for {!r}; got {!r}'.format(marker, buf[-200:]))
            buf += self.ser.read(1)
        return buf[:-len(marker)]

    def enter(self):
        # A Ctrl-C can land in a timer callback and be swallowed there, so
        # interrupt more than once.
        for _ in range(3):
            self.ser.write(b'\r\x03')
            time.sleep(0.2)
            self.ser.write(b'\x03')
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.ser.write(b'\x01')
            try:
                self._read_until(b'raw REPL; CTRL-B to exit\r\n>', 3)
                return
            except TimeoutError:
                continue
        raise DeviceError('could not interrupt the firmware and reach the raw REPL')

    def exec(self, code, timeout=20):
        data = code.encode()
        for i in range(0, len(data), 256):
            self.ser.write(data[i:i + 256])
        self.ser.write(b'\x04')
        self._read_until(b'OK', 5)
        out = self._read_until(b'\x04', timeout)
        err = self._read_until(b'\x04', timeout)
        self._read_until(b'>', 5)
        if err:
            raise DeviceError(err.decode(errors='replace').strip())
        return out.decode(errors='replace')

    def eval(self, expr):
        return ast.literal_eval(self.exec('print(repr({}))'.format(expr)).strip())

    def start(self, code):
        """Send code without waiting for it to finish (e.g. a reset)."""
        self.ser.write(code.encode() + b'\x04')
        time.sleep(0.5)


def find_port(wait_s=0):
    deadline = time.monotonic() + wait_s
    while True:
        for pattern in PORT_GLOBS:
            ports = glob.glob(pattern)
            if len(ports) > 1:
                raise DeviceError('more than one board matches {}; pass --port'.format(pattern))
            if ports:
                return ports[0]
        if time.monotonic() >= deadline:
            raise DeviceError('no RP2040 found at {}. Is the USB cable connected?'
                              .format(' or '.join(PORT_GLOBS)))
        time.sleep(0.1)


def firmware_files(version):
    """(path on the board, contents) for every file the firmware ships."""
    files = []
    for root, dirs, names in os.walk(MICRO_DIR):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in sorted(names):
            rel = os.path.relpath(os.path.join(root, name), MICRO_DIR).replace(os.sep, '/')
            if rel in NOT_SHIPPED or name.endswith('.pyc'):
                continue
            with open(os.path.join(root, name), 'rb') as f:
                files.append((rel, f.read()))
    files.append(('version.py', 'VERSION = {!r}\n'.format(version).encode()))
    return files


def sha256(data):
    return hashlib.sha256(data).hexdigest()


ATTEMPTS = 3


def retrying(repl, what, fn):
    """Run fn, retrying after a protocol or device error.

    The serial link occasionally corrupts a byte, which can lose a REPL
    marker or garble a command. Re-entering the raw REPL resynchronises.
    Every step is safe to repeat, and staged files are verified by hash, so
    a retry can't leave corrupted data on the board.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return fn()
        except (DeviceError, TimeoutError, ValueError, SyntaxError) as err:
            if attempt == ATTEMPTS:
                raise DeviceError('{} failed {} times; last error: {}'.format(what, ATTEMPTS, err))
            print('{} failed ({}); retrying'.format(what, err))
            time.sleep(0.5)
            repl.enter()
            repl.exec(DEVICE_HELPERS)


def stage(repl, path, data):
    repl.exec('_mkdirs({0!r}); _f = open({1!r}, "wb")'.format(path, path + '.new'))
    for i in range(0, len(data), CHUNK):
        b64 = binascii.b2a_base64(data[i:i + CHUNK], newline=False)
        repl.exec('_f.write(binascii.a2b_base64({!r}))'.format(b64))
    repl.exec('_f.close()')
    got = repl.eval('_hash({!r})'.format(path + '.new'))
    if got != sha256(data):
        raise DeviceError('{} did not verify after writing (board has {}, expected {})'
                          .format(path, got, sha256(data)))


def wait_for_boot(version, since):
    deadline = time.monotonic() + BOOT_WAIT_S
    needle = "'version': {!r}".format(version)
    while time.monotonic() < deadline:
        time.sleep(3)
        log = subprocess.run(['journalctl', '-u', 'roboat-monitor', '--since', since,
                              '--no-pager', '-o', 'cat'],
                             capture_output=True, text=True).stdout
        for line in log.splitlines():
            if "'src': 'status'" in line and needle in line and "'event': 'boot'" in line:
                return line
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--version', required=True, help='commit being deployed')
    parser.add_argument('--port', help='USB serial port (default: found automatically)')
    parser.add_argument('--serial', metavar='PORT',
                        help="flash over the Pi link's UART instead of USB; stops "
                             'roboat-monitor while flashing')
    parser.add_argument('--wait', type=int, default=0, metavar='SECONDS',
                        help='wait this long for the board to appear, then interrupt it at once')
    parser.add_argument('--reset-delay', type=int, metavar='SECONDS',
                        help='reset the board this long after flashing instead of now, '
                             'and skip the boot check')
    args = parser.parse_args()

    files = firmware_files(args.version)
    paths = [p for p, _ in files]
    if args.serial:
        monitor('stop')
        try:
            since = flash(args, files, paths, args.serial)
        finally:
            monitor('start')  # also needed to see the boot status below
    else:
        port = args.port or find_port(args.wait)
        if args.wait:
            time.sleep(0.3)  # let the port settle after enumeration
        since = flash(args, files, paths, port)

    if args.reset_delay:
        print('The board resets itself in {} s.'.format(args.reset_delay))
        return 0
    print('Board reset; waiting for the boot status message...')
    line = wait_for_boot(args.version, since)
    if line is None:
        print('No boot status with version {} within {} s. Check the monitor journal and the '
              'board.'.format(args.version, BOOT_WAIT_S), file=sys.stderr)
        return BOOT_CHECK_FAILED
    print('Firmware {} is running: {}'.format(args.version, line))
    return 0


def monitor(action):
    subprocess.run(['sudo', 'systemctl', action, 'roboat-monitor'], check=True)


def flash(args, files, paths, port):
    """Stage, verify, and install the files, then reset the board (now, or
    after --reset-delay). Returns the time just before the reset."""
    repl = RawRepl(port)
    try:
        if args.serial:
            repl.ser.write(MAINTENANCE_COMMAND)
            time.sleep(1.0)
        repl.enter()
        repl.exec(DEVICE_HELPERS)
        on_board = retrying(repl, 'Reading the board',
                            lambda: repl.eval('[_hash(p) for p in {!r}]'.format(paths)))
        changed = [(p, d) for (p, d), h in zip(files, on_board) if h != sha256(d)]
        previous = retrying(repl, 'Reading the manifest', lambda: repl.eval('_manifest()'))
        stale = sorted(set(previous if previous is not None else LEGACY_FILES)
                       - set(paths) - STATE_FILES)

        print('{} of {} files changed{}'.format(
            len(changed), len(files),
            ': ' + ', '.join(p for p, _ in changed) if changed else ''))
        for path, data in changed:
            retrying(repl, 'Staging ' + path, lambda: stage(repl, path, data))
        print('All changed files staged and verified.')

        # Safe to repeat: a file already moved into place has no .new left.
        install = '\n'.join(
            ['for p in {!r}:'.format([p for p, _ in changed]),
             '    try:',
             '        os.stat(p + ".new")',
             '    except OSError:',
             '        continue',
             '    os.rename(p + ".new", p)',
             'for p in {!r}:'.format(stale),
             '    try:',
             '        os.remove(p)',
             '    except OSError:',
             '        pass',
             'with open({!r}, "w") as f:'.format(MANIFEST),
             '    f.write({!r})'.format('\n'.join(paths) + '\n')])
        retrying(repl, 'Installing the files', lambda: repl.exec(install))
        if stale:
            print('Removed from the board: ' + ', '.join(stale))

        since = time.strftime('%Y-%m-%d %H:%M:%S')
        if args.reset_delay:
            repl.start('import time, machine\ntime.sleep({})\nmachine.reset()'
                       .format(args.reset_delay))
        else:
            repl.start('import machine\nmachine.reset()')
        return since
    finally:
        repl.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except DeviceError as e:
        print('Flash failed: {}'.format(e), file=sys.stderr)
        sys.exit(1)
