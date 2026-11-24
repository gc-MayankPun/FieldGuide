"""Plain data classes shared between the threads and modules."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in camera-frame pixels


@dataclass
class Frame:
    image: np.ndarray  # BGR, as delivered by OpenCV
    index: int
    timestamp: float


@dataclass
class Detection:
    track_id: int
    label: str
    confidence: float
    box: Box


@dataclass
class Track:
    id: int
    label: str          # stabilised label shown to the user
    confidence: float
    box: Box
    stable: bool
    frames_seen: int
    raw_label: str = ""  # label predicted on the latest frame


@dataclass
class Result:
    frame_index: int
    tracks: list[Track]
    inference_ms: float
    inference_fps: float
    backend: str
    timestamp: float


@dataclass(frozen=True)
class Video:
    title: str
    channel: str
    video_id: str
    thumbnail: str = ""
    curated: bool = False

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class Entry:
    label: str
    display_name: str
    category: str = "general"
    summary: str = ""
    steps: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    tutorial_queries: list[str] = field(default_factory=list)
    curated_videos: list[Video] = field(default_factory=list)
    generic: bool = False  # True when no knowledge-base entry exists
