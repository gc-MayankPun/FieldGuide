
"""Threaded text-to-speech using espeak-ng."""
from __future__ import annotations

import queue
import shutil
import subprocess
import threading

from PySide6.QtCore import QObject, Signal


class SpeechWorker(QObject):
    state_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self._executable = shutil.which("espeak-ng")
        self.available = self._executable is not None

        self._queue = queue.Queue()
        self._thread = None
        self._process = None

        self._lock = threading.RLock()
        self._speaking = False
        self._closed = False

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._speaking

    def _set_speaking(self, value: bool) -> None:
        with self._lock:
            if self._speaking == value:
                return

            self._speaking = value

        self.state_changed.emit(value)

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._run,
            name="FieldGuide-Speech",
            daemon=True,
        )

        self._thread.start()

    def _run(self) -> None:
        while True:
            task = self._queue.get()

            if task is None:
                break

            try:
                with self._lock:
                    if self._closed:
                        break

                    self._process = subprocess.Popen(
                        [self._executable, task],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                    )

                    process = self._process

                _, stderr = process.communicate()

                if process.returncode != 0 and not self._closed:
                    message = stderr.strip() or "espeak-ng playback failed."
                    self.error_occurred.emit(message)

            except Exception as exc:
                if not self._closed:
                    self.error_occurred.emit(str(exc))

            finally:
                with self._lock:
                    self._process = None

                self._set_speaking(False)

        self._set_speaking(False)

    def speak_steps(self, title: str, steps: list[str]) -> None:
        if not self.available or self._closed or not steps:
            return

        with self._lock:
            if self._speaking or self._closed:
                return

            self._speaking = True

        text = title + ". " + " ".join(
            f"Step {index}. {step}"
            for index, step in enumerate(steps, 1)
        )

        self.state_changed.emit(True)

        self._ensure_thread()
        self._queue.put(text)

    def stop(self) -> None:
        # Playback is intentionally allowed to finish naturally.
        pass

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            self._closed = True
            process = self._process

        # Terminate playback when the application closes.
        if process is not None and process.poll() is None:
            process.terminate()

        self._queue.put(None)

        if self._thread is not None:
            self._thread.join(timeout=3)

        self._set_speaking(False)
