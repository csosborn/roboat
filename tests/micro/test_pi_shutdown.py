import pi_shutdown as ps


def run(listening_until_ms, end_ms, step_ms=1000):
    s = ps.PiShutdown()
    s.start(0, "low_battery")
    requests = []
    for t in range(0, end_ms + 1, step_ms):
        if s.step(t, t < listening_until_ms, requests.append):
            return t, requests, s.timed_out
    return None, requests, None


def test_power_cut_once_the_pi_has_been_quiet_long_enough():
    done_at, requests, timed_out = run(listening_until_ms=20000, end_ms=200000)
    assert done_at == 20000 + ps.HALT_MARGIN_MS and not timed_out
    assert requests[0] == "low_battery"
    assert len(requests) == done_at // ps.REQUEST_INTERVAL_MS + 1


def test_a_pi_that_ignores_the_request_is_cut_after_the_timeout():
    done_at, _, timed_out = run(listening_until_ms=10 ** 9, end_ms=200000)
    assert done_at == ps.TIMEOUT_MS and timed_out
