import threading
import time

from fieldguide.geometry import box_to_view, fit_rect, hit_test, view_to_frame
from fieldguide.models import Track
from fieldguide.slots import LatestSlot


def test_slot_keeps_only_newest():
    s = LatestSlot()
    for i in range(5):
        s.put(i)
    item, v = s.latest()
    assert item == 4 and v == 5


def test_wait_new_times_out_then_wakes():
    s = LatestSlot()
    item, v = s.wait_new(0, timeout=0.05)
    assert item is None and v == 0
    threading.Timer(0.05, lambda: s.put("x")).start()
    item, v = s.wait_new(0, timeout=1.0)
    assert item == "x" and v == 1


def test_letterbox_roundtrip():
    s, ox, oy = fit_rect(1280, 720, 800, 800)
    assert abs(s - 0.625) < 1e-9 and ox == 0 and oy > 0
    x, y = view_to_frame(*box_to_view((100, 100, 200, 200), s, ox, oy)[:2], s, ox, oy)
    assert abs(x - 100) < 1e-6 and abs(y - 100) < 1e-6


def _t(i, box, stable=True):
    return Track(i, "cup", 0.9, box, stable, 10)


def test_hit_test_prefers_smallest_stable_box():
    big, small = _t(1, (0, 0, 100, 100)), _t(2, (40, 40, 60, 60))
    assert hit_test([big, small], 50, 50).id == 2
    assert hit_test([big, small], 5, 5).id == 1
    assert hit_test([big, small], 500, 5) is None
    assert hit_test([_t(3, (0, 0, 10, 10), stable=False)], 5, 5) is None
