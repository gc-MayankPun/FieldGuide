"""Letterbox maths shared by the video widget and its tests (no Qt needed)."""
from __future__ import annotations

from .models import Box, Track


def fit_rect(frame_w: int, frame_h: int, view_w: float, view_h: float) -> tuple[float, float, float]:
    """Return (scale, offset_x, offset_y) that centre the frame inside the view."""
    if frame_w <= 0 or frame_h <= 0 or view_w <= 0 or view_h <= 0:
        return 1.0, 0.0, 0.0
    scale = min(view_w / frame_w, view_h / frame_h)
    return scale, (view_w - frame_w * scale) / 2, (view_h - frame_h * scale) / 2


def view_to_frame(x: float, y: float, scale: float, ox: float, oy: float) -> tuple[float, float]:
    return (x - ox) / scale, (y - oy) / scale


def box_to_view(box: Box, scale: float, ox: float, oy: float) -> Box:
    x1, y1, x2, y2 = box
    return x1 * scale + ox, y1 * scale + oy, x2 * scale + ox, y2 * scale + oy


def hit_test(tracks: list[Track], fx: float, fy: float, only_stable: bool = True) -> Track | None:
    """Topmost (smallest) box that contains the point."""
    best: Track | None = None
    best_area = float("inf")
    for t in tracks:
        if only_stable and not t.stable:
            continue
        x1, y1, x2, y2 = t.box
        if x1 <= fx <= x2 and y1 <= fy <= y2:
            area = (x2 - x1) * (y2 - y1)
            if area < best_area:
                best, best_area = t, area
    return best
