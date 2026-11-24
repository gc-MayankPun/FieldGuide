"""Owns the capture and inference threads and starts/stops them together."""
from __future__ import annotations

from typing import Callable

from .capture import CaptureThread
from .config import Config
from .detector import Detector, DetectorProtocol, InferenceThread
from .slots import LatestSlot
from .stabiliser import LabelStabiliser


class Pipeline:
    def __init__(self, cfg: Config, source: str | None = None,
                 detector_factory: Callable[[], DetectorProtocol] | None = None) -> None:
        self.cfg = cfg
        self.source = source
        self.detector_factory = detector_factory or (
            lambda: Detector(cfg.detector, cfg.tracking, cfg.base_dir))
        self.conf = cfg.detector.conf
        self.results = LatestSlot()
        self.capture: CaptureThread | None = None
        self.inference: InferenceThread | None = None
        self._detector: DetectorProtocol | None = None

    @property
    def running(self) -> bool:
        return self.capture is not None

    def start(self) -> None:
        if self.running:
            return
        t = self.cfg.tracking
        stabiliser = LabelStabiliser(t.label_window, t.stable_frames, t.switch_ratio,
                                     t.lost_frames, t.box_smoothing)
        if self._detector is None:           # keep the loaded model between restarts
            self._detector = self.detector_factory()
        else:
            self._detector.reset()
        self.results = LatestSlot()
        self.capture = CaptureThread(self.cfg.camera, self.source)
        self.inference = InferenceThread(self.capture.slot, self.results, self._detector,
                                         stabiliser, lambda: self.conf)
        self.capture.start()
        self.inference.start()

    def stop(self) -> None:
        for th in (self.capture, self.inference):
            if th is not None:
                th.stop()
        for th in (self.capture, self.inference):
            if th is not None:
                th.join(timeout=3.0)
        self.capture = None
        self.inference = None

    def errors(self) -> list[str]:
        out = []
        if self.capture is not None and self.capture.error:
            out.append(self.capture.error)
        if self.inference is not None and self.inference.error:
            out.append(self.inference.error)
        return out
