from fieldguide.config import load_config


def test_defaults_without_file():
    cfg, warns = load_config(None)
    assert cfg.detector.imgsz == 416 and warns == []


def test_missing_file_uses_defaults(tmp_path):
    cfg, warns = load_config(tmp_path / "nope.toml")
    assert cfg.detector.conf == 0.5 and warns


def test_values_clamped_wrong_types_and_unknown_keys(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[detector]\nconf = 5.0\nimgsz = "big"\nbogus = 1\n[nosuch]\nx = 1\n'
                 '[tracking]\nstable_frames = 0\n[ui]\nvoice = true\n')
    cfg, warns = load_config(p)
    assert cfg.detector.conf == 0.95
    assert cfg.detector.imgsz == 416          # wrong type -> default
    assert cfg.tracking.stable_frames == 1    # clamped
    assert cfg.ui.voice is True
    text = " ".join(warns)
    assert "bogus" in text and "nosuch" in text and "imgsz" in text


def test_invalid_toml(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("this is = = not toml")
    cfg, warns = load_config(p)
    assert cfg.camera.width == 1280 and warns


def test_relative_paths_use_config_folder(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("")
    cfg, _ = load_config(p)
    assert cfg.path("data/x.json") == tmp_path / "data" / "x.json"


def test_shipped_config_is_clean():
    from pathlib import Path
    cfg, warns = load_config(Path(__file__).resolve().parents[1] / "config.toml")
    assert warns == []
