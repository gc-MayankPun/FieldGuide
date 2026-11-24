"""Load and validate config.toml. Bad values never crash the app: they fall back to defaults."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720


@dataclass
class DetectorConfig:
    model: str = "yolo11n.pt"
    imgsz: int = 416
    conf: float = 0.50
    iou: float = 0.70
    max_det: int = 20
    device: str = "auto"


@dataclass
class TrackingConfig:
    tracker: str = "bytetrack.yaml"
    stable_frames: int = 6
    label_window: int = 10
    switch_ratio: float = 1.2
    lost_frames: int = 30
    box_smoothing: float = 0.6


@dataclass
class GuidanceConfig:
    knowledge_base: str = "data/knowledge_base.json"
    skip_labels: list = field(default_factory=lambda: ["person"])


@dataclass
class TutorialConfig:
    api_key_env: str = "YOUTUBE_API_KEY"
    max_results: int = 5
    cache_days: int = 7
    language: str = "en"
    cache_db: str = "data/cache.sqlite3"


@dataclass
class UIConfig:
    voice: bool = False


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    guidance: GuidanceConfig = field(default_factory=GuidanceConfig)
    tutorials: TutorialConfig = field(default_factory=TutorialConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    base_dir: Path = field(default_factory=Path.cwd)

    def path(self, value: str) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else self.base_dir / p


# (min, max) clamps for numeric settings
_BOUNDS = {
    ("camera", "index"): (0, 20), ("camera", "width"): (160, 3840), ("camera", "height"): (120, 2160),
    ("detector", "imgsz"): (160, 1280), ("detector", "conf"): (0.05, 0.95), ("detector", "iou"): (0.1, 0.95),
    ("detector", "max_det"): (1, 300),
    ("tracking", "stable_frames"): (1, 60), ("tracking", "label_window"): (1, 60),
    ("tracking", "switch_ratio"): (1.0, 5.0), ("tracking", "lost_frames"): (1, 600),
    ("tracking", "box_smoothing"): (0.05, 1.0),
    ("tutorials", "max_results"): (1, 10), ("tutorials", "cache_days"): (0, 365),
}


def _coerce(value, default):
    """Return value converted to the type of default, or raise ValueError."""
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        raise ValueError("expected true/false")
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError("expected a whole number")
        return int(value)
    if isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("expected a number")
        return float(value)
    if isinstance(default, str):
        if not isinstance(value, str):
            raise ValueError("expected text")
        return value
    if isinstance(default, list):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError("expected a list of text values")
        return list(value)
    return value


def load_config(path: str | Path | None = None) -> tuple[Config, list[str]]:
    """Return (config, warnings). A missing file gives defaults."""
    cfg = Config()
    warnings: list[str] = []
    if path is None:
        return cfg, warnings
    p = Path(path)
    cfg.base_dir = p.resolve().parent
    if not p.exists():
        warnings.append(f"Config file not found: {p}. Using defaults.")
        return cfg, warnings
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        warnings.append(f"Could not read {p.name}: {exc}. Using defaults.")
        return cfg, warnings

    for section, table in data.items():
        target = getattr(cfg, section, None)
        if target is None or not isinstance(table, dict) or section == "base_dir":
            warnings.append(f"Unknown section [{section}] ignored.")
            continue
        known = {f.name for f in fields(target)}
        for key, value in table.items():
            if key not in known:
                warnings.append(f"Unknown key {section}.{key} ignored.")
                continue
            default = getattr(target, key)
            try:
                value = _coerce(value, default)
            except ValueError as exc:
                warnings.append(f"{section}.{key}: {exc}; using default {default!r}.")
                continue
            bounds = _BOUNDS.get((section, key))
            if bounds is not None:
                clamped = min(max(value, bounds[0]), bounds[1])
                if clamped != value:
                    warnings.append(f"{section}.{key}={value} out of range; using {clamped}.")
                value = type(default)(clamped)
            setattr(target, key, value)
    return cfg, warnings
