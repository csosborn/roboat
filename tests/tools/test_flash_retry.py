import pytest

import rp2040_flash as fl


class FlakyRepl:
    """Fails the first `failures` calls the way a corrupted byte does."""

    def __init__(self, failures):
        self.failures = failures
        self.reentered = 0

    def call(self):
        if self.failures:
            self.failures -= 1
            raise TimeoutError("waiting for b'\\x04'; got b'>'")
        return "ok"

    def enter(self):
        self.reentered += 1

    def exec(self, code):
        pass


def test_a_transient_link_error_is_retried(monkeypatch):
    monkeypatch.setattr(fl.time, 'sleep', lambda s: None)
    repl = FlakyRepl(failures=2)
    assert fl.retrying(repl, 'Reading the board', repl.call) == "ok"
    assert repl.reentered == 2


def test_a_persistent_error_gives_up_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(fl.time, 'sleep', lambda s: None)
    repl = FlakyRepl(failures=10)
    with pytest.raises(fl.DeviceError, match='Reading the board failed 3 times'):
        fl.retrying(repl, 'Reading the board', repl.call)
