from scheduler import Scheduler


def test_one_shot_runs_once_when_due():
    s, ran = Scheduler(), []
    s.after(100, lambda: ran.append("a"), now_ms=0)
    s.run_due(99)
    assert ran == []
    s.run_due(100)
    s.run_due(500)
    assert ran == ["a"]


def test_periodic_repeats_without_catching_up():
    s, ran = Scheduler(), []
    s.every(10, lambda: ran.append(1), now_ms=0)
    for t in (10, 15, 20, 100, 105, 110):
        s.run_due(t)
    assert len(ran) == 4  # at 10, 20, 100, 110


def test_tasks_can_schedule_more_tasks():
    s, ran = Scheduler(), []
    s.after(10, lambda: s.after(10, lambda: ran.append("second"), now_ms=10), now_ms=0)
    s.run_due(10)
    assert ran == []
    s.run_due(20)
    assert ran == ["second"]


def test_reconnect_schedule_survives_until_due():
    # The bug this replaces: one-shot work silently never ran.
    s, ran = Scheduler(), []
    for delay in (20000, 60000):
        s.after(delay, lambda: ran.append("usb"), now_ms=0)
    for t in range(0, 61000, 500):
        s.run_due(t)
    assert ran == ["usb", "usb"]
