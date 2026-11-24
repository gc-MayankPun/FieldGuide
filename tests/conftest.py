import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from fieldguide.models import Detection


class FakeDetector:
    """Stands in for YOLO so the pipeline can be tested without a model or camera."""
    backend = "fake"

    def __init__(self, script=None, delay=0.0):
        self.script = script or (lambda n: [Detection(1, "laptop", 0.9, (10, 10, 100, 100))])
        self.delay = delay
        self.calls = 0
        self.loaded = False

    def load(self):
        self.loaded = True

    def track(self, image, conf):
        import time
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        return [d for d in self.script(self.calls) if d.confidence >= conf]

    def reset(self):
        self.calls = 0


@pytest.fixture
def fake_detector():
    return FakeDetector


@pytest.fixture
def video_file(tmp_path):
    import cv2
    p = tmp_path / "clip.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 240))
    for i in range(60):
        frame = np.full((240, 320, 3), 40, np.uint8)
        cv2.rectangle(frame, (20 + i, 40), (120 + i, 160), (0, 255, 0), -1)
        w.write(frame)
    w.release()
    return str(p)
