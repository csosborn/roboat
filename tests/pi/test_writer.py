from writer import QueuedWriter


class FlakyInflux:
    def __init__(self):
        self.up = False
        self.points = []

    def write(self, point):
        if not self.up:
            raise ConnectionError("not ready")
        self.points.append(point)


def test_points_survive_an_outage_in_order():
    db = FlakyInflux()
    w = QueuedWriter(db.write)
    w.write(1)
    w.write(2)
    assert db.points == []
    db.up = True
    w.write(3)
    assert db.points == [1, 2, 3]


def test_long_outage_drops_oldest_first():
    db = FlakyInflux()
    w = QueuedWriter(db.write, max_queued=3)
    for p in range(5):
        w.write(p)
    db.up = True
    w.flush()
    assert db.points == [2, 3, 4]
