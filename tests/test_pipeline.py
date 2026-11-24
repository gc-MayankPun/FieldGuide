import time

from fieldguide.config import load_config
from fieldguide.models import Detection
from fieldguide.pipeline import Pipeline


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def make(video_file, detector):
    cfg, _ = load_config(None)
    return Pipeline(cfg, source=video_file, detector_factory=lambda: detector)


def test_end_to_end_with_video_file(video_file, fake_detector):
    det = fake_detector()
    pl = make(video_file, det)
    pl.start()
    try:
        assert wait_for(lambda: pl.results.latest()[0] is not None)
        assert wait_for(lambda: pl.results.latest()[0].tracks and pl.results.latest()[0].tracks[0].stable)
        r = pl.results.latest()[0]
        assert r.tracks[0].label == "laptop" and r.backend == "fake"
        assert pl.capture.width == 320 and pl.capture.height == 240
        assert det.loaded and pl.errors() == []
    finally:
        pl.stop()
    assert not pl.running


def test_slow_detector_never_queues_frames(video_file, fake_detector):
    det = fake_detector(delay=0.15)               # much slower than the 30 fps video
    pl = make(video_file, det)
    pl.start()
    try:
        assert wait_for(lambda: pl.capture.finished, timeout=5)   # capture is not held back
        time.sleep(0.4)
        frames_read = pl.capture.slot.latest()[1]
        assert frames_read >= 50 and det.calls < frames_read / 2  # frames were skipped, not queued
    finally:
        pl.stop()


def test_confidence_slider_applies_live(video_file, fake_detector):
    det = fake_detector(script=lambda n: [Detection(1, "cup", 0.6, (0, 0, 9, 9))])
    pl = make(video_file, det)
    pl.conf = 0.9
    pl.start()
    try:
        assert wait_for(lambda: pl.results.latest()[0] is not None)
        assert pl.results.latest()[0].tracks == []
        pl.conf = 0.3
        assert wait_for(lambda: pl.results.latest()[0].tracks != [])
    finally:
        pl.stop()


def test_camera_error_reported(fake_detector):
    cfg, _ = load_config(None)
    pl = Pipeline(cfg, source="/nonexistent/video.mp4", detector_factory=lambda: fake_detector())
    pl.start()
    try:
        assert wait_for(lambda: pl.errors())
        assert "Could not open" in pl.errors()[0]
    finally:
        pl.stop()


def test_model_load_failure_reported(video_file):
    class Broken:
        backend = "x"
        def load(self): raise RuntimeError("weights missing")
        def track(self, *a): return []
        def reset(self): pass
    pl = make(video_file, Broken())
    pl.start()
    try:
        assert wait_for(lambda: any("weights missing" in e for e in pl.errors()))
    finally:
        pl.stop()


def test_restart_works_and_stop_releases_threads(video_file, fake_detector):
    pl = make(video_file, fake_detector())
    for _ in range(2):
        pl.start()
        assert wait_for(lambda: pl.results.latest()[0] is not None)
        cap, inf = pl.capture, pl.inference
        pl.stop()
        assert not cap.is_alive() and not inf.is_alive()
