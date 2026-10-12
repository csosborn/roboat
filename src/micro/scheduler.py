import time


class Scheduler:
    """Runs delayed and periodic work from the main loop.

    Used instead of machine.Timer: a Timer that nothing keeps a reference to
    can be garbage-collected before it fires, which silently cancels it. Work
    run from here also never interrupts other work.
    """

    def __init__(self):
        self.tasks_ = []  # [due_ms, fn, period_ms or None]

    def after(self, delay_ms, fn, now_ms=None):
        now = time.ticks_ms() if now_ms is None else now_ms
        self.tasks_.append([time.ticks_add(now, delay_ms), fn, None])

    def every(self, period_ms, fn, now_ms=None):
        now = time.ticks_ms() if now_ms is None else now_ms
        self.tasks_.append([time.ticks_add(now, period_ms), fn, period_ms])

    def run_due(self, now_ms):
        due = [t for t in self.tasks_ if time.ticks_diff(now_ms, t[0]) >= 0]
        for task in due:
            if task[2] is None:
                self.tasks_.remove(task)
            else:
                task[0] = time.ticks_add(now_ms, task[2])
            task[1]()
