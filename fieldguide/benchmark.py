"""Measure the detector on a recorded video or the webcam, without the UI.

    python -m fieldguide.benchmark --video clip.mp4 --frames 300
Prints inference time (mean / 95th percentile), inference FPS and how often labels change
with and without label voting. Use these numbers in the report's evaluation chapter.
"""
from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import cv2

from .config import load_config
from .detector import Detector
from .stabiliser import LabelStabiliser


def run(config: str | None, video: str | None, frames: int, camera: int) -> dict:
    cfg, _ = load_config(config)
    cap = cv2.VideoCapture(video if video else camera)
    if not cap.isOpened():
        raise SystemExit("Could not open the video or camera.")
    det = Detector(cfg.detector, cfg.tracking, cfg.base_dir)
    det.load()
    t = cfg.tracking
    stab = LabelStabiliser(t.label_window, t.stable_frames, t.switch_ratio, t.lost_frames, t.box_smoothing)
    times, raw_changes, shown_changes = [], 0, 0
    last_raw: dict[int, str] = {}
    last_shown: dict[int, str] = {}
    first_stable: dict[int, int] = {}
    n, start = 0, time.perf_counter()
    while n < frames:
        ok, img = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        dets = det.track(img, cfg.detector.conf)
        tracks = stab.update(dets)
        times.append((time.perf_counter() - t0) * 1000)
        n += 1
        for d in dets:
            if d.track_id in last_raw and last_raw[d.track_id] != d.label:
                raw_changes += 1
            last_raw[d.track_id] = d.label
        for tr in tracks:
            if tr.id in last_shown and last_shown[tr.id] != tr.label:
                shown_changes += 1
            last_shown[tr.id] = tr.label
            if tr.stable:
                first_stable.setdefault(tr.id, n)
    total = time.perf_counter() - start
    cap.release()
    if not times:
        raise SystemExit("No frames were processed.")
    times_sorted = sorted(times)
    p95 = times_sorted[min(len(times_sorted) - 1, int(0.95 * len(times_sorted)))]
    out = {"frames": n, "backend": det.backend, "mean_ms": statistics.mean(times), "p95_ms": p95,
           "fps": n / total, "label_changes_raw": raw_changes, "label_changes_with_voting": shown_changes,
           "tracks_seen": len(last_raw)}
    print(f"Backend:                {out['backend']}")
    print(f"Frames processed:       {out['frames']}")
    print(f"Inference mean / p95:   {out['mean_ms']:.1f} ms / {out['p95_ms']:.1f} ms")
    print(f"Throughput:             {out['fps']:.1f} frames/s")
    print(f"Tracks seen:            {out['tracks_seen']}")
    print(f"Label changes (raw):    {out['label_changes_raw']}")
    print(f"Label changes (voting): {out['label_changes_with_voting']}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.toml" if Path("config.toml").exists() else None)
    ap.add_argument("--video", default=None)
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--camera", type=int, default=0)
    a = ap.parse_args()
    run(a.config, a.video, a.frames, a.camera)


if __name__ == "__main__":
    main()
