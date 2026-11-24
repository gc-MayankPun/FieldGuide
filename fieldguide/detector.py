"""YOLO detector with built-in tracking, and the inference thread that drives it."""
from __future__ import annotations

import threading
import time
from typing import Callable, Protocol

from .config import DetectorConfig, TrackingConfig
from .models import Detection, Result
from .slots import LatestSlot
from .stabiliser import LabelStabiliser


class DetectorProtocol(Protocol):
    backend: str

    def load(self) -> None: ...
    def track(self, image, conf: float) -> list[Detection]: ...
    def reset(self) -> None: ...


class Detector:
    """Wraps Ultralytics YOLO + ByteTrack. Imported lazily so the UI starts quickly."""

    def __init__(self, cfg: DetectorConfig, tracking: TrackingConfig, base_dir=None) -> None:
        self.cfg = cfg
        self.tracking = tracking
        self.base_dir = base_dir
        self.model = None
        self.backend = "not loaded"

    def _resolve_model(self) -> str:
        if self.base_dir is not None:
            p = (self.base_dir / self.cfg.model)
            if p.exists():
                return str(p)           # your own fine-tuned weights next to config.toml
        return self.cfg.model           # otherwise let Ultralytics download it

    def load(self) -> None:
        if self.model is not None:
            return
        from ultralytics import YOLO  # lazy import on purpose
        self.model = YOLO(self._resolve_model())
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        if self.cfg.device not in ("auto", ""):
            return self.cfg.device
        try:
            import torch
            if torch.cuda.is_available():
                return f"cuda:0 ({torch.cuda.get_device_name(0)})"
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def track(self, image, conf: float) -> list[Detection]:
        c, t = self.cfg, self.tracking
        kwargs = dict(imgsz=c.imgsz, conf=conf, iou=c.iou, max_det=c.max_det, persist=True,
                      tracker=t.tracker, verbose=False)
        if c.device not in ("auto", ""):
            kwargs["device"] = c.device
        res = self.model.track(image, **kwargs)[0]
        boxes = res.boxes
        if boxes is None or boxes.id is None:
            return []
        ids = boxes.id.int().tolist()
        cls = boxes.cls.int().tolist()
        confs = boxes.conf.tolist()
        xyxy = boxes.xyxy.tolist()
        names = self.model.names
        return [Detection(i, names[k], float(p), tuple(b)) for i, k, p, b in zip(ids, cls, confs, xyxy)]

    def reset(self) -> None:
        """Forget tracker state (used when the camera is restarted)."""
        try:
            if self.model is not None:
                self.model.predictor = None
        except Exception:
            pass


class InferenceThread(threading.Thread):
    """Takes the newest frame, detects, tracks, stabilises and publishes the result."""

    def __init__(self, frame_slot: LatestSlot, result_slot: LatestSlot, detector: DetectorProtocol,
                 stabiliser: LabelStabiliser, get_conf: Callable[[], float]) -> None:
        super().__init__(name="inference", daemon=True)
        self.frames = frame_slot
        self.results = result_slot
        self.detector = detector
        self.stabiliser = stabiliser
        self.get_conf = get_conf
        self.stop_event = threading.Event()
        self.status = "loading"      # loading | running | error
        self.error: str | None = None
        self.fps = 0.0
        self.last_ms = 0.0

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            self.detector.load()
        except Exception as exc:  # model missing, no internet, bad weights...
            self.status = "error"
            self.error = f"Could not load the model: {exc}"
            return
        self.status = "running"
        last_version, last_done = 0, None
        while not self.stop_event.is_set():
            frame, last_version = self.frames.wait_new(last_version, timeout=0.2)
            if frame is None:
                continue
            t0 = time.perf_counter()
            try:
                dets = self.detector.track(frame.image, self.get_conf())
            except Exception as exc:
                self.status, self.error = "error", f"Detection failed: {exc}"
                time.sleep(0.5)
                continue
            tracks = self.stabiliser.update(dets)
            done = time.perf_counter()
            self.last_ms = (done - t0) * 1000.0
            if last_done is not None and done > last_done:
                inst = 1.0 / (done - last_done)
                self.fps = inst if self.fps == 0 else 0.8 * self.fps + 0.2 * inst
            last_done = done
            self.status, self.error = "running", None
            self.results.put(Result(frame.index, tracks, self.last_ms, self.fps,
                                    self.detector.backend, time.time()))
