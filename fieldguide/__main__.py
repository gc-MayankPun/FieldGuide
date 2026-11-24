"""python -m fieldguide [--config config.toml] [--camera N] [--video file.mp4]"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(prog="fieldguide", description="Real-time object recognition with guidance.")
    ap.add_argument("--config", default=None, help="path to config.toml (default: ./config.toml if present)")
    ap.add_argument("--camera", type=int, default=None, help="camera index, overrides config")
    ap.add_argument("--video", default=None, help="use a video file instead of the webcam")
    ap.add_argument("--start", action="store_true", help="start the camera immediately")
    args = ap.parse_args()
    config = args.config or ("config.toml" if Path("config.toml").exists() else None)
    from .app import run
    return run(config, camera=args.camera, video=args.video, autostart=args.start)


if __name__ == "__main__":
    raise SystemExit(main())
