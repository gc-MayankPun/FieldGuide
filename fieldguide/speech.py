"""Optional offline text-to-speech. Silently unavailable if pyttsx3 or a speech engine is missing."""
from __future__ import annotations

import queue
import threading


class SpeechWorker:
    def __init__(self) -> None:
        try:
            import pyttsx3  # noqa: F401
            self.available = True
        except Exception:
            self.available = False
        self._q: queue.Queue = queue.Queue()
        self._generation = 0
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
        except Exception:
            self.available = False
            return
        while True:
            gen, text = self._q.get()
            if text is None:
                return
            if gen != self._generation:
                continue                       # selection changed: skip stale sentences
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                continue

    def speak_steps(self, title: str, steps: list[str]) -> None:
        if not self.available:
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="speech", daemon=True)
            self._thread.start()
        self._generation += 1
        gen = self._generation
        self._q.put((gen, title))
        for i, s in enumerate(steps, 1):
            self._q.put((gen, f"Step {i}. {s}"))

    def stop(self) -> None:
        self._generation += 1                  # pending sentences are dropped

    def close(self) -> None:
        self.stop()
        if self._thread is not None:
            self._q.put((0, None))
