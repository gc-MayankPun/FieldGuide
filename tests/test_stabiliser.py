from fieldguide.models import Detection
from fieldguide.stabiliser import LabelStabiliser


def det(i, label, conf=0.8, box=(0, 0, 10, 10)):
    return Detection(i, label, conf, box)


def test_single_wrong_frame_does_not_rename():
    s = LabelStabiliser(window=10, stable_frames=3)
    for _ in range(6):
        s.update([det(1, "cup")])
    out = s.update([det(1, "vase", 0.6)])
    assert out[0].label == "cup" and out[0].raw_label == "vase"


def test_sustained_change_switches_label():
    s = LabelStabiliser(window=6, stable_frames=3)
    for _ in range(4):
        s.update([det(1, "bottle")])
    label = None
    for _ in range(10):
        label = s.update([det(1, "can", 0.9)])[0].label
    assert label == "can"


def test_stable_flag_after_enough_frames():
    s = LabelStabiliser(stable_frames=4)
    flags = [s.update([det(1, "cup")])[0].stable for _ in range(5)]
    assert flags == [False, False, False, True, True]


def test_same_class_objects_keep_identity():
    s = LabelStabiliser()
    for _ in range(3):
        out = s.update([det(1, "cup", box=(0, 0, 10, 10)), det(2, "cup", box=(50, 0, 60, 10))])
    assert {t.id for t in out} == {1, 2}
    assert out[0].frames_seen == 3


def test_stale_tracks_are_forgotten():
    s = LabelStabiliser(lost_frames=2)
    s.update([det(1, "cup")])
    for _ in range(4):
        s.update([])
    assert s._states == {}
    assert s.update([det(1, "cup")])[0].frames_seen == 1


def test_box_smoothing_moves_gradually():
    s = LabelStabiliser(box_smoothing=0.5)
    s.update([det(1, "cup", box=(0, 0, 10, 10))])
    out = s.update([det(1, "cup", box=(10, 0, 20, 10))])
    assert out[0].box[0] == 5.0
