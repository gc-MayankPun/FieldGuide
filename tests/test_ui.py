import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from fieldguide.config import load_config
from fieldguide.guidance import KnowledgeBase
from fieldguide.models import Detection
from fieldguide.pipeline import Pipeline
from fieldguide.tutorials import TutorialService
from fieldguide.ui.main_window import MainWindow
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def pump(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build(app, tmp_path, video_file, fake_detector, script=None):
    cfg, _ = load_config(ROOT / "config.toml")
    kb = KnowledgeBase.load(ROOT / "data" / "knowledge_base.json")
    tut = TutorialService(cfg.tutorials, tmp_path / "c.db", fetch=lambda u: b'{"items": []}')
    det = fake_detector(script=script)
    pl = Pipeline(cfg, source=video_file, detector_factory=lambda: det)
    return MainWindow(cfg, kb, tut, pl), pl


def test_window_shows_video_boxes_and_guidance(app, tmp_path, video_file, fake_detector, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    win, pl = build(app, tmp_path, video_file, fake_detector)
    win.show()
    win.start_camera()
    try:
        pump(app, 1.5)
        assert win.start_action.text() == "Stop camera"
        assert win.video._image is not None and win.video._tracks
        track = win.video._tracks[0]
        assert track.stable
        win.on_object_clicked(track.id)
        pump(app, 0.8)
        assert "Laptop" in win.panel.title.text()
        assert "Open the lid" in win.panel.body.text()
        assert "API key" in win.panel.note.text()          # fallback message without a key
        win.on_object_clicked(-1)
        assert win.panel.title.text() == "FieldGuide"
    finally:
        win.close()


def test_click_maps_through_letterbox(app, tmp_path, video_file, fake_detector):
    win, pl = build(app, tmp_path, video_file, fake_detector)
    win.resize(1000, 700)
    win.show()
    win.start_camera()
    try:
        pump(app, 1.2)
        v = win.video
        from fieldguide.geometry import fit_rect, box_to_view
        s, ox, oy = fit_rect(*v._size, v.width(), v.height())
        x1, y1, x2, y2 = box_to_view(v._tracks[0].box, s, ox, oy)
        clicked = []
        v.object_clicked.connect(clicked.append)
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF((x1 + x2) / 2, (y1 + y2) / 2),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        v.mousePressEvent(ev)
        assert clicked == [v._tracks[0].id]
    finally:
        win.close()


def test_person_gets_no_instructions(app, tmp_path, video_file, fake_detector):
    script = lambda n: [Detection(7, "person", 0.9, (10, 10, 200, 200))]
    win, pl = build(app, tmp_path, video_file, fake_detector, script)
    win.show()
    win.start_camera()
    try:
        pump(app, 1.2)
        win.on_object_clicked(7)
        assert "not for people" in win.panel.body.text()
    finally:
        win.close()


def test_unknown_object_gets_generic_card_and_stop_is_clean(app, tmp_path, video_file, fake_detector):
    script = lambda n: [Detection(3, "hair drier", 0.9, (10, 10, 200, 200))]
    win, pl = build(app, tmp_path, video_file, fake_detector, script)
    win.show()
    win.start_camera()
    pump(app, 1.2)
    win.on_object_clicked(3)
    assert "Hair Drier" in win.panel.title.text()
    win.stop_camera()
    assert not pl.running and win.start_action.text() == "Start camera"
    win.close()


def test_missing_camera_shows_banner(app, tmp_path, fake_detector):
    win, pl = build(app, tmp_path, "/no/such/file.mp4", fake_detector)
    win.show()
    win.start_camera()
    try:
        pump(app, 0.8)
        assert win.banner.isVisible() and "Could not open" in win.banner.text()
    finally:
        win.close()
