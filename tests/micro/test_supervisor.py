import os

import pytest

import supervisor as sv


@pytest.fixture(autouse=True)
def device_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_safe_mode_after_repeated_unhealthy_boots():
    results = [sv.record_boot() for _ in range(sv.SAFE_MODE_AFTER_BOOTS + 1)]
    assert [safe for _, safe in results] == [False] * sv.SAFE_MODE_AFTER_BOOTS + [True]
    assert results[-1][0] == sv.SAFE_MODE_AFTER_BOOTS + 1


def test_healthy_run_resets_boot_count():
    for _ in range(sv.SAFE_MODE_AFTER_BOOTS):
        sv.record_boot()
    sv.mark_healthy()
    assert sv.record_boot() == (1, False)


def test_corrupt_boot_count_is_treated_as_zero(device_fs):
    (device_fs / sv.BOOTCOUNT_FILE).write_text("garbage")
    assert sv.record_boot() == (1, False)


def test_crash_log_records_traceback_and_rotates(device_fs, monkeypatch):
    monkeypatch.setattr(sv, 'CRASH_LOG_MAX_BYTES', 200)
    for i in range(5):
        try:
            raise OSError("i2c failure {}".format(i))
        except OSError as e:
            sv.record_crash(e, uptime_ms=1000 * i)
    log = (device_fs / sv.CRASH_LOG).read_text()
    assert "i2c failure 4" in log
    assert "Traceback" in log
    assert (device_fs / sv.CRASH_LOG_OLD).exists()


def test_nowdt_flag(device_fs):
    assert not sv.wdt_disabled()
    (device_fs / sv.NOWDT_FLAG).write_text("")
    assert sv.wdt_disabled()


def test_watchdog_fed_only_while_main_loop_alive():
    live = sv.Liveness(now_ms=0)
    assert live.should_feed(sv.LIVENESS_MS - 1)
    assert not live.should_feed(sv.LIVENESS_MS + 1)
    live.alive(10000)
    assert live.should_feed(10500)


def test_maintenance_window_holds_off_watchdog_then_expires():
    live = sv.Liveness(now_ms=0)
    live.start_maintenance(now_ms=0, seconds=60)
    assert live.should_feed(59000)
    assert not live.should_feed(61000)


class FakeUSBDevice:
    """Models MicroPython's runtime USBDevice: it starts with no built-in
    driver, and refuses to activate without a driver or a config()."""
    BUILTIN_NONE = 0
    BUILTIN_DEFAULT = 1
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
            cls.instance._active = True
            cls.instance._builtin = cls.BUILTIN_NONE
        return cls.instance

    def active(self, value=None):
        if value is None:
            return self._active
        if value and self._builtin == self.BUILTIN_NONE:
            raise OSError(22)
        self._active = value

    @property
    def builtin_driver(self):
        return self._builtin

    @builtin_driver.setter
    def builtin_driver(self, value):
        if self._active:
            raise OSError(1)
        self._builtin = value


def test_usb_reconnect_leaves_usb_active_with_the_builtin_driver(monkeypatch):
    import machine
    FakeUSBDevice.instance = None
    monkeypatch.setattr(machine, 'USBDevice', FakeUSBDevice, raising=False)
    sv.usb_reconnect()
    dev = FakeUSBDevice()
    assert dev.active() is True
    assert dev.builtin_driver == FakeUSBDevice.BUILTIN_DEFAULT
