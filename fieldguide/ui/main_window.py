
"""Main window: toolbar, live video, guidance panel and status bar."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSlider,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from ..config import Config
from ..guidance import KnowledgeBase
from ..models import Result
from ..pipeline import Pipeline
from ..speech import SpeechWorker
from ..tutorials import TutorialResult, TutorialService
from .side_panel import SidePanel
from .video_widget import VideoWidget


class _Bridge(QObject):
    tutorials_ready = Signal(int, object)


class MainWindow(QMainWindow):

    def __init__(
        self,
        cfg: Config,
        kb: KnowledgeBase,
        tutorials: TutorialService,
        pipeline: Pipeline,
        warnings: list[str] | None = None,
    ) -> None:

        super().__init__()

        self.cfg = cfg
        self.kb = kb
        self.tutorials = tutorials
        self.pipeline = pipeline

        self.speech = SpeechWorker()

        self.setWindowTitle("FieldGuide")
        self.resize(1440, 850)
        self.setMinimumSize(1050, 650)

        self._selected_id = -1
        self._request_id = 0
        self._last_frame_version = -1
        self._last_result: Result | None = None

        self._bridge = _Bridge()
        self._bridge.tutorials_ready.connect(self._on_tutorials)

        # --------------------------------------------------
        # Toolbar
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Video and side panel
        # --------------------------------------------------

        self.video = VideoWidget()
        self.video.object_clicked.connect(self.on_object_clicked)

        self.panel = SidePanel()

        # Manual speech playback only.
        self.panel.speak_requested.connect(self._toggle_speech)

        # Synchronize button state with actual playback state.
        self.speech.state_changed.connect(self._on_speech_state)
        self.speech.error_occurred.connect(self._on_speech_error)

        # Keep the button initially disabled if speech is unavailable.
        self.panel.speak_button.setEnabled(self.speech.available)

        if not self.speech.available:
            self.panel.speak_button.setToolTip(
                "Install pyttsx3 and espeak-ng to enable speech."
            )

        self.banner = QLabel()
        self.banner.setStyleSheet(
            "background:#fdecea; color:#8a1c12; padding:6px;"
        )
        self.banner.setWordWrap(True)
        self.banner.hide()

        left = QWidget()

        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.banner)
        ll.addWidget(self.video, 1)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(5)
        split.setChildrenCollapsible(False)

        self.panel.setMinimumWidth(340)
        self.panel.setMaximumWidth(440)

        split.addWidget(left)
        split.addWidget(self.panel)

        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)

        split.setSizes([1060, 380])

        self.setCentralWidget(split)

        # --------------------------------------------------
        # Status bar
        # --------------------------------------------------

        self.status = QLabel("Ready.")
        self.statusBar().addWidget(self.status, 1)

        if warnings:
            self.statusBar().showMessage(
                "; ".join(warnings)[:300],
                8000,
            )

        # --------------------------------------------------
        # Refresh timer
        # --------------------------------------------------

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._status_tick = 0

    # ------------------------------------------------------
    # Speech controls
    # ------------------------------------------------------

    def _toggle_speech(self, title: str, steps: list[str]) -> None:
        """Start instruction playback once."""

        if self.speech.is_speaking:
            return

        if steps:
            self.speech.speak_steps(title, steps)

    def _on_speech_state(self, speaking: bool) -> None:
        """Disable the button for the duration of playback."""

        button = self.panel.speak_button

        button.setEnabled(not speaking)

        if speaking:
            button.setText("  Reading instructions...")
            button.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_MediaPlay
                )
            )
        else:
            button.setText("  Listen to instructions")
            button.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_MediaPlay
                )
            )

    def _on_speech_error(self, message: str) -> None:
        self.statusBar().showMessage(
            f"Speech error: {message}",
            5000,
        )

    # ------------------------------------------------------
    # Camera
    # ------------------------------------------------------

    def toggle_camera(self) -> None:

        if self.pipeline.running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self) -> None:

        self.banner.hide()
        self._selected_id = -1

        self.speech.stop()
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

    # ------------------------------------------------------
    # Video updates
    # ------------------------------------------------------

    def _tick(self) -> None:

        pl = self.pipeline

        if not pl.running:
            return

        cap = pl.capture
        inf = pl.inference

        frame, version = cap.slot.latest()

        if frame is not None and version != self._last_frame_version:

            self._last_frame_version = version
            self.video.set_frame(frame.image)

        result, _ = pl.results.latest()

        if result is not None:
            self._last_result = result

        tracks = (
            self._last_result.tracks
            if self._last_result
            else []
        )

        self.video.set_tracks(tracks, self._selected_id)
        self.video.update()

        errs = pl.errors()

        if errs:
            self.banner.setText(
                "  ".join(errs)
                + "   (Press Stop, then Start to retry.)"
            )
            self.banner.show()
        else:
            self.banner.hide()

        if cap.finished and not errs:
            self.status.setText("Video finished.")

        self._status_tick += 1

        if self._status_tick % 10 == 0 and not (
            cap.finished and not errs
        ):

            r = self._last_result

            model_state = (
                "loading model..."
                if inf.status == "loading"
                else ""
            )

            if r:
                self.status.setText(
                    f"Backend: {r.backend}   |   "
                    f"Camera: {cap.width}x{cap.height} "
                    f"@ {cap.fps:.0f} fps   |   "
                    f"Inference: {r.inference_ms:.0f} ms "
                    f"({r.inference_fps:.0f}/s)   |   "
                    f"Tracked: {len(tracks)}"
                )
            else:
                self.status.setText(
                    f"Camera: {cap.width}x{cap.height} "
                    f"@ {cap.fps:.0f} fps   {model_state}"
                )

    # ------------------------------------------------------
    # Object selection
    # ------------------------------------------------------

    def on_object_clicked(self, track_id: int) -> None:

        self.speech.stop()

        if track_id < 0:

            self._selected_id = -1
            self.panel.show_idle()
            return

        track = next(
            (
                t
                for t in (
                    self._last_result.tracks
                    if self._last_result
                    else []
                )
                if t.id == track_id
            ),
            None,
        )

        if track is None:
            return

        self._selected_id = track_id

        if track.label in self.cfg.guidance.skip_labels:

            self.panel.show_message(
                track.label.title(),
                "FieldGuide gives guidance for objects, not for people.",
            )
            return

        entry = self.kb.entry_or_generic(track.label)

        self.panel.show_entry(entry, track.confidence)

        # No automatic speech here.
        # Playback starts only when the user clicks Listen.

        # Fetch tutorials in a background thread.
        self._request_id += 1
        rid = self._request_id

        def work() -> None:

            res = self.tutorials.find(entry)

            self._bridge.tutorials_ready.emit(rid, res)

        threading.Thread(
            target=work,
            name="tutorials",
            daemon=True,
        ).start()

    # ------------------------------------------------------
    # Tutorial results
    # ------------------------------------------------------

    def _on_tutorials(
        self,
        rid: int,
        result: TutorialResult,
    ) -> None:

        if rid == self._request_id and self._selected_id >= 0:
            self.panel.set_tutorials(result)

    # ------------------------------------------------------
    # Confidence slider
    # ------------------------------------------------------

    def _on_slider(self, value: int) -> None:

        self.pipeline.conf = value / 100.0
        self.slider_label.setText(f" {value}%  ")

    # ------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------

    def keyPressEvent(self, event) -> None:

        if event.key() == Qt.Key.Key_Escape:
            self.on_object_clicked(-1)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------

    def closeEvent(self, event) -> None:

        self.timer.stop()

        self.speech.close()
        self.pipeline.stop()

        super().closeEvent(event)
