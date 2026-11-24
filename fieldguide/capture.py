"""Camera (or video file) reader running in its own thread."""
from __future__ import annotations

import threading
import time

import cv2

from .config import CameraConfig
from .models import Frame
from .slots import LatestSlot


class CaptureThread(threading.Thread):
    """Reads frames as fast as the camera delivers them and keeps only the newest one."""

    def __init__(self, cfg: CameraConfig, source: str | None = None) -> None:
        super().__init__(name="capture", daemon=True)
        self.cfg = cfg
        self.source = source           # video file path; None = webcam
        self.slot = LatestSlot()
        self.stop_event = threading.Event()
        self.error: str | None = None
        self.opened = threading.Event()
        self.fps = 0.0
        self.width = 0
        self.height = 0
        self.dropped = 0
        self.finished = False          # True when a video file reached its end

    # -- helpers ---------------------------------------------------------
    def _open(self) -> cv2.VideoCapture | None:
        cap = cv2.VideoCapture(self.source) if self.source else cv2.VideoCapture(self.cfg.index)
        if not cap.isOpened():
            cap.release()
            return None
        if not self.source:
            try:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # allows 720p30 on most webcams
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return cap

    def stop(self) -> None:
        self.stop_event.set()

    # -- main loop -------------------------------------------------------
    def run(self) -> None:
        cap = self._open()
        if cap is None:
            what = self.source or f"camera {self.cfg.index}"
            self.error = (f"Could not open {what}. Check that it is plugged in and not used by "
                          f"another program, then press Start again.")
            self.opened.set()
            return
        self.opened.set()
        file_fps = cap.get(cv2.CAP_PROP_FPS) if self.source else 0.0
        index, failures, last = 0, 0, time.perf_counter()
        try:
            while not self.stop_event.is_set():
                ok, image = cap.read()
                if not ok or image is None:
                    if self.source:
                        self.finished = True
                        break
                    failures += 1
                    self.dropped += 1
                    if failures >= 30:  # camera lost: try to reopen once a second
                        self.error = "Camera connection lost. Trying to reconnect..."
                        cap.release()
                        while not self.stop_event.is_set():
                            time.sleep(1.0)
                            cap = self._open()
                            if cap is not None:
                                self.error, failures = None, 0
                                break
                        if cap is None:
                            break
                    else:
                        time.sleep(0.01)
                    continue
                failures = 0
                index += 1
                self.slot.put(Frame(image=image, index=index, timestamp=time.time()))
                now = time.perf_counter()
                dt = now - last
                last = now
                if dt > 0:
                    inst = 1.0 / dt
                    self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
                if file_fps and file_fps > 0:      # play video files at their own speed
                    time.sleep(max(0.0, 1.0 / file_fps - (time.perf_counter() - now)))
        finally:
            if cap is not None:
                cap.release()
