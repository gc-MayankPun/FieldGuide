"""Single-item slots: the newest value overwrites the old one, nothing queues up."""
from __future__ import annotations

import threading
from typing import Any


class LatestSlot:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._item: Any = None
        self._version = 0

    def put(self, item: Any) -> None:
        with self._cond:
            self._item = item
            self._version += 1
            self._cond.notify_all()

    def latest(self) -> tuple[Any, int]:
        """Non-blocking read for the UI. Does not consume the item."""
        with self._cond:
            return self._item, self._version

    def wait_new(self, last_version: int, timeout: float = 0.2) -> tuple[Any, int]:
        """Block until an item newer than last_version exists (or timeout)."""
        with self._cond:
            self._cond.wait_for(lambda: self._version > last_version, timeout)
            if self._version > last_version:
                return self._item, self._version
            return None, last_version

    def clear(self) -> None:
        with self._cond:
            self._item = None
            self._version += 1
