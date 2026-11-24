"""Main window: toolbar, live video, guidance panel and status bar."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QLabel, QMainWindow, QSlider, QSplitter, QToolBar, QVBoxLayout, QWidget)

from ..config import Config
from ..guidance import KnowledgeBase
from ..models import Result
from ..pipeline import Pipeline
from ..speech import SpeechWorker
from ..tutorials import TutorialResult, TutorialService
from .side_panel import SidePanel
from .video_widget import VideoWidget


class _Bridge(QObject):
    tutorials_ready = Signal(int, object)   # request id, TutorialResult


class MainWindow(QMainWindow):
    def __init__(self, cfg: Config, kb: KnowledgeBase, tutorials: TutorialService,
                 pipeline: Pipeline, warnings: list[str] | None = None) -> None:
        super().__init__()
        self.cfg, self.kb, self.tutorials, self.pipeline = cfg, kb, tutorials, pipeline
        self.speech = SpeechWorker()
        self.setWindowTitle("FieldGuide")
        self.resize(1280, 760)
        self._selected_id = -1
        self._request_id = 0
        self._last_frame_version = -1
        self._last_result: Result | None = None
        self._bridge = _Bridge()
        self._bridge.tutorials_ready.connect(self._on_tutorials)

        # toolbar
        tb = QToolBar("Controls")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.start_action = QAction("Start camera", self)
        self.start_action.setShortcut(QKeySequence("Ctrl+R"))
        self.start_action.triggered.connect(self.toggle_camera)
        tb.addAction(self.start_action)
        tb.addSeparator()
        tb.addWidget(QLabel("  Confidence: "))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(20, 90)
        self.slider.setValue(int(round(pipeline.conf * 100)))
        self.slider.setFixedWidth(160)
        self.slider.valueChanged.connect(self._on_slider)
        tb.addWidget(self.slider)
        self.slider_label = QLabel(f" {self.slider.value()}%  ")
        tb.addWidget(self.slider_label)
        tb.addSeparator()
        self.voice_box = QCheckBox("Speak steps")
        self.voice_box.setChecked(cfg.ui.voice and self.speech.available)
        self.voice_box.setEnabled(self.speech.available)
        if not self.speech.available:
            self.voice_box.setToolTip("Install pyttsx3 (and espeak-ng on Linux) to enable speech.")
        tb.addWidget(self.voice_box)

        # centre
        self.video = VideoWidget()
        self.video.object_clicked.connect(self.on_object_clicked)
        self.panel = SidePanel()
        self.banner = QLabel()
        self.banner.setStyleSheet("background:#fdecea; color:#8a1c12; padding:6px;")
        self.banner.setWordWrap(True)
        self.banner.hide()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.banner)
        ll.addWidget(self.video, 1)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.panel)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 2)
        self.setCentralWidget(split)

        self.status = QLabel("Ready.")
        self.statusBar().addWidget(self.status, 1)
        if warnings:
            self.statusBar().showMessage("; ".join(warnings)[:300], 8000)

        self.timer = QTimer(self)
        self.timer.setInterval(30)           # ~33 redraws/s, independent of inference speed
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._status_tick = 0

    # -- camera ----------------------------------------------------------
    def toggle_camera(self) -> None:
        if self.pipeline.running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self) -> None:
        self.banner.hide()
        self._selected_id = -1
        self.panel.show_idle()
        self.video.set_message("Starting camera...")
        self.video.update()
        self._last_frame_version = -1
        self._last_result = None
        self.pipeline.start()
        self.start_action.setText("Stop camera")

    def stop_camera(self) -> None:
        self.speech.stop()
        self.pipeline.stop()
        self.video.clear()
        self.video.set_message("Camera is off. Press Start.")
        self.video.update()
        self.panel.show_idle()
        self._selected_id = -1
        self.start_action.setText("Start camera")
        self.status.setText("Stopped.")

    # -- per-tick drawing --------------------------------------------------
    def _tick(self) -> None:
        pl = self.pipeline
        if not pl.running:
            return
        cap, inf = pl.capture, pl.inference
        frame, version = cap.slot.latest()
        if frame is not None and version != self._last_frame_version:
            self._last_frame_version = version
            self.video.set_frame(frame.image)
        result, _ = pl.results.latest()
        if result is not None:
            self._last_result = result
        tracks = self._last_result.tracks if self._last_result else []
        self.video.set_tracks(tracks, self._selected_id)
        self.video.update()

        errs = pl.errors()
        if errs:
            self.banner.setText("  ".join(errs) + "   (Press Stop, then Start to retry.)")
            self.banner.show()
        else:
            self.banner.hide()
        if cap.finished and not errs:
            self.status.setText("Video finished.")

        self._status_tick += 1
        if self._status_tick % 10 == 0 and not (cap.finished and not errs):
            r = self._last_result
            model_state = "loading model..." if inf.status == "loading" else ""
            self.status.setText(
                f"Backend: {r.backend if r else '-'}   |   Camera: {cap.width}x{cap.height} @ {cap.fps:.0f} fps   |   "
                f"Inference: {r.inference_ms:.0f} ms ({r.inference_fps:.0f}/s)   |   Tracked: {len(tracks)}"
                if r else f"Camera: {cap.width}x{cap.height} @ {cap.fps:.0f} fps   {model_state}")

    # -- selection and guidance ---------------------------------------------
    def on_object_clicked(self, track_id: int) -> None:
        self.speech.stop()
        if track_id < 0:
            self._selected_id = -1
            self.panel.show_idle()
            return
        track = next((t for t in (self._last_result.tracks if self._last_result else []) if t.id == track_id), None)
        if track is None:
            return
        self._selected_id = track_id
        if track.label in self.cfg.guidance.skip_labels:
            self.panel.show_message(track.label.title(),
                                    "FieldGuide gives guidance for objects, not for people.")
            return
        entry = self.kb.entry_or_generic(track.label)
        self.panel.show_entry(entry, track.confidence)
        if self.voice_box.isChecked() and entry.steps:
            self.speech.speak_steps(entry.display_name, entry.steps)
        self._request_id += 1
        rid = self._request_id

        def work() -> None:
            res = self.tutorials.find(entry)
            self._bridge.tutorials_ready.emit(rid, res)

        threading.Thread(target=work, name="tutorials", daemon=True).start()

    def _on_tutorials(self, rid: int, result: TutorialResult) -> None:
        if rid == self._request_id and self._selected_id >= 0:   # ignore stale answers
            self.panel.set_tutorials(result)

    def _on_slider(self, value: int) -> None:
        self.pipeline.conf = value / 100.0
        self.slider_label.setText(f" {value}%  ")

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.on_object_clicked(-1)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.speech.close()
        self.pipeline.stop()
        super().closeEvent(event)
