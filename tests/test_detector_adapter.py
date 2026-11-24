"""Checks the YOLO adapter against a stand-in that has the same result shape as Ultralytics."""
from fieldguide.config import DetectorConfig, TrackingConfig
from fieldguide.detector import Detector


class T:  # tensor-like
    def __init__(self, v): self.v = v
    def int(self): return T([int(x) for x in self.v])
    def tolist(self): return self.v


class Boxes:
    def __init__(self, ids, cls, conf, xyxy):
        self.id, self.cls, self.conf, self.xyxy = (T(ids) if ids is not None else None), T(cls), T(conf), T(xyxy)


class Res:
    def __init__(self, boxes): self.boxes = boxes


class StubModel:
    names = {0: "person", 41: "cup"}

    def __init__(self, boxes): self._boxes, self.kwargs = boxes, None
    def track(self, image, **kw):
        self.kwargs = kw
        return [Res(self._boxes)]


def make(boxes):
    d = Detector(DetectorConfig(), TrackingConfig())
    d.model = StubModel(boxes)
    return d


def test_adapter_converts_results_and_passes_settings():
    d = make(Boxes([5, 6], [41, 0], [0.9, 0.7], [[1, 2, 3, 4], [5, 6, 7, 8]]))
    out = d.track(object(), 0.4)
    assert [(x.track_id, x.label, x.box) for x in out] == [(5, "cup", (1, 2, 3, 4)), (6, "person", (5, 6, 7, 8))]
    kw = d.model.kwargs
    assert kw["imgsz"] == 416 and kw["conf"] == 0.4 and kw["persist"] is True and kw["tracker"] == "bytetrack.yaml"


def test_no_tracked_objects_gives_empty_list():
    assert make(Boxes(None, [], [], [])).track(object(), 0.5) == []
    assert make(None).track(object(), 0.5) == []
