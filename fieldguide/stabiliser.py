"""Label voting, box smoothing and the 'stable' flag on top of the tracker."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .models import Detection, Track


@dataclass
class _State:
    history: deque
    displayed: str = ""
    frames_seen: int = 0
    last_frame: int = 0
    box: tuple | None = None


class LabelStabiliser:
    def __init__(self, window: int = 10, stable_frames: int = 6, switch_ratio: float = 1.2,
                 lost_frames: int = 30, box_smoothing: float = 0.6) -> None:
        self.window = max(1, window)
        self.stable_frames = max(1, stable_frames)
        self.switch_ratio = max(1.0, switch_ratio)
        self.lost_frames = max(1, lost_frames)
        self.alpha = min(1.0, max(0.05, box_smoothing))
        self._frame_no = 0
        self._states: dict[int, _State] = {}

    def reset(self) -> None:
        self._frame_no = 0
        self._states.clear()

    def update(self, detections: list[Detection]) -> list[Track]:
        self._frame_no += 1
        out: list[Track] = []
        for d in detections:
            st = self._states.get(d.track_id)
            if st is None:
                st = _State(history=deque(maxlen=self.window))
                self._states[d.track_id] = st
            st.history.append((d.label, d.confidence))
            st.frames_seen += 1
            st.last_frame = self._frame_no

            scores: dict[str, float] = defaultdict(float)
            for label, conf in st.history:
                scores[label] += conf
            best = max(scores, key=scores.get)
            if not st.displayed or st.displayed not in scores:
                st.displayed = best
            elif best != st.displayed and scores[best] > self.switch_ratio * scores[st.displayed]:
                st.displayed = best

            confs = [c for lbl, c in st.history if lbl == st.displayed]
            conf = sum(confs) / len(confs)

            if st.box is None:
                st.box = tuple(d.box)
            else:
                a = self.alpha
                st.box = tuple(a * n + (1 - a) * o for n, o in zip(d.box, st.box))

            out.append(Track(id=d.track_id, label=st.displayed, confidence=conf, box=st.box,
                             stable=st.frames_seen >= self.stable_frames,
                             frames_seen=st.frames_seen, raw_label=d.label))
        stale = [i for i, s in self._states.items() if self._frame_no - s.last_frame > self.lost_frames]
        for i in stale:
            del self._states[i]
        return out
