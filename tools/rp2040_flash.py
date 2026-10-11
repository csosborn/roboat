#!/usr/bin/env python3
"""Flash the RP2040's MicroPython files from this checkout.

Runs on the Pi, which the RP2040 is attached to over USB.

1. Interrupt the running firmware and enter the raw REPL. Current firmware
   treats the interrupt as maintenance: its watchdog is held off for 15
   minutes and then resets the board, so an abandoned flash recovers itself.
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
PORT_GLOB = '/dev/serial/by-id/usb-MicroPython_*'
NOT_SHIPPED = {'install.sh', 'notes.md', 'version.py'}
MANIFEST = 'deploy_manifest'
# Runtime state the firmware keeps on flash. A deploy never deletes these.
STATE_FILES = {'bootcount', 'pi_power', 'crash.log', 'crash.log.1', 'nowdt', MANIFEST}
# Left on the board by work that predates the manifest.
LEGACY_FILES = ['statemachine.py', 'relay_test.txt', 'relay_test2.txt', 'relay_test3.txt']
CHUNK = 768
BOOT_WAIT_S = 45

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


def find_port():
    ports = glob.glob(PORT_GLOB)
    if len(ports) != 1:
        raise DeviceError('expected one RP2040 at {}, found {}. Is the USB cable connected?'
                          .format(PORT_GLOB, len(ports) or 'none'))
    return ports[0]


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
    parser.add_argument('--reset-delay', type=int, metavar='SECONDS',
                        help='reset the board this long after flashing instead of now, '
                             'and skip the boot check')
    args = parser.parse_args()

    files = firmware_files(args.version)
    paths = [p for p, _ in files]
    repl = RawRepl(find_port())
    try:
        repl.enter()
        repl.exec(DEVICE_HELPERS)
        on_board = repl.eval('[_hash(p) for p in {!r}]'.format(paths))
        changed = [(p, d) for (p, d), h in zip(files, on_board) if h != sha256(d)]
        previous = repl.eval('_manifest()')
        stale = sorted(set(previous if previous is not None else LEGACY_FILES)
                       - set(paths) - STATE_FILES)

        print('{} of {} files changed{}'.format(
            len(changed), len(files),
            ': ' + ', '.join(p for p, _ in changed) if changed else ''))
        for path, data in changed:
            stage(repl, path, data)
        print('All changed files staged and verified.')

        repl.exec('\n'.join(
            ['for p in {!r}:'.format([p for p, _ in changed]),
             '    os.rename(p + ".new", p)',
             'for p in {!r}:'.format(stale),
             '    try:',
             '        os.remove(p)',
             '    except OSError:',
             '        pass',
             'with open({!r}, "w") as f:'.format(MANIFEST),
             '    f.write({!r})'.format('\n'.join(paths) + '\n')]))
        if stale:
            print('Removed from the board: ' + ', '.join(stale))

        since = time.strftime('%Y-%m-%d %H:%M:%S')
        if args.reset_delay:
            repl.start('import time, machine\ntime.sleep({})\nmachine.reset()'
                       .format(args.reset_delay))
            print('The board resets itself in {} s.'.format(args.reset_delay))
            return 0
        repl.start('import machine\nmachine.reset()')
    finally:
        repl.close()

    print('Board reset; waiting for the boot status message...')
    line = wait_for_boot(args.version, since)
    if line is None:
        print('No boot status with version {} within {} s. Check the monitor journal and the '
              'board.'.format(args.version, BOOT_WAIT_S), file=sys.stderr)
        return 1
    print('Firmware {} is running: {}'.format(args.version, line))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except DeviceError as e:
        print('Flash failed: {}'.format(e), file=sys.stderr)
        sys.exit(1)
