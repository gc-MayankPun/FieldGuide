
"""Local neural text-to-speech using Piper."""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class SpeechWorker(QObject):
    state_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self._executable = (
            shutil.which("piper-tts")
            or shutil.which("piper")
        )
        self._player = shutil.which("aplay")

        self._model = Path(
            os.environ.get(
                "FIELDGUIDE_PIPER_MODEL",
                "~/.local/share/fieldguide/voices/"
                "en_US-lessac-medium.onnx",
            )
        ).expanduser()

        self._length_scale = float(
            os.environ.get("FIELDGUIDE_PIPER_LENGTH_SCALE", "1.0")
        )

        self._sample_rate = 22050
        self._queue: queue.Queue[str | None] = queue.Queue()

        self._thread: threading.Thread | None = None
        self._piper_process: subprocess.Popen | None = None
        self._player_process: subprocess.Popen | None = None

        self._lock = threading.RLock()
        self._speaking = False
        self._closed = False
        self._cancelled = False

        self.available = self._check_setup()

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._speaking

    def _check_setup(self) -> bool:
        if not self._executable:
            return False

        if not self._player:
            return False

        if not self._model.is_file():
            return False

        config_path = Path(f"{self._model}.json")

        if not config_path.is_file():
            return False

        try:
            with config_path.open("r", encoding="utf-8") as file:
                config = json.load(file)

            self._sample_rate = int(config["audio"]["sample_rate"])

            if self._sample_rate <= 0:
                return False

        except (OSError, ValueError, KeyError, TypeError):
            return False

        return True

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
            name="FieldGuide-Piper",
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _build_text(title: str, steps: list[str]) -> str:
        parts = []

        if title.strip():
            parts.append(f"{title.strip()}.")

        for index, step in enumerate(steps, start=1):
            cleaned = step.strip()

            if cleaned:
                parts.append(f"Step {index}. {cleaned}.")

        return " ".join(parts)

    def speak_steps(self, title: str, steps: list[str]) -> None:
        if not self.available or not steps:
            return

        text = self._build_text(title, steps)

        if not text:
            return

        with self._lock:
            if self._closed or self._speaking:
                return

            self._speaking = True
            self._cancelled = False

        self.state_changed.emit(True)

        self._ensure_thread()
        self._queue.put(text)

    def _run(self) -> None:
        while True:
            text = self._queue.get()

            if text is None:
                break

            try:
                self._play(text)

            except Exception as exc:
                with self._lock:
                    cancelled = self._cancelled or self._closed

                if not cancelled:
                    self.error_occurred.emit(str(exc))

            finally:
                self._clear_processes()
                self._set_speaking(False)

    def _play(self, text: str) -> None:
        player = subprocess.Popen(
            [
                self._player,
                "-q",
                "-t", "raw",
                "-f", "S16_LE",
                "-r", str(self._sample_rate),
                "-c", "1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        with self._lock:
            if self._cancelled or self._closed:
                player.terminate()
                return

            self._player_process = player

        try:
            piper = subprocess.Popen(
                [
                    self._executable,
                    "--model", str(self._model),
                    "--output-raw",
                    "--length_scale", str(self._length_scale),
                ],
                stdin=subprocess.PIPE,
                stdout=player.stdin,
                stderr=subprocess.PIPE,
            )

            with self._lock:
                if self._cancelled or self._closed:
                    piper.terminate()
                    player.terminate()
                    return

                self._piper_process = piper

            # The parent must close its copy so the player receives EOF
            # after Piper finishes writing audio.
            player.stdin.close()

            _, piper_error = piper.communicate(
                input=text.encode("utf-8")
            )

            player.wait()
            player_error = player.stderr.read()

            with self._lock:
                cancelled = self._cancelled or self._closed

            if cancelled:
                return

            if piper.returncode != 0:
                message = piper_error.decode(
                    "utf-8", errors="replace"
                ).strip()

                raise RuntimeError(
                    message or "Piper speech synthesis failed."
                )

            if player.returncode != 0:
                message = player_error.decode(
                    "utf-8", errors="replace"
                ).strip()

                raise RuntimeError(
                    message or "Audio playback failed."
                )

        finally:
            self._terminate_processes()

    def _terminate_processes(self) -> None:
        with self._lock:
            processes = (
                self._piper_process,
                self._player_process,
            )

        for process in processes:
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass

        for process in processes:
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()

    def _clear_processes(self) -> None:
        with self._lock:
            self._piper_process = None
            self._player_process = None

    def stop(self) -> None:
        with self._lock:
            if not self._speaking:
                return

            self._cancelled = True

        self._terminate_processes()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            self._closed = True
            self._cancelled = True

        self._terminate_processes()
        self._queue.put(None)

        if self._thread is not None:
            self._thread.join(timeout=3)

        self._set_speaking(False)
