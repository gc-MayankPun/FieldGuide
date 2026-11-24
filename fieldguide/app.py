"""Wire everything together and start the Qt application."""
from __future__ import annotations

import sys
from pathlib import Path


def run(config_path: str | None, camera: int | None = None, video: str | None = None,
        autostart: bool = False) -> int:
    # Load project-local secrets before services read environment variables.
    from dotenv import load_dotenv

    env_file = Path(config_path).resolve().parent / ".env" if config_path else Path.cwd() / ".env"
    load_dotenv(dotenv_path=env_file)

    from PySide6.QtWidgets import QApplication

    from .config import load_config
    from .guidance import KnowledgeBase
    from .pipeline import Pipeline
    from .tutorials import TutorialService
    from .ui.main_window import MainWindow

    cfg, warnings = load_config(config_path)
    if camera is not None:
        cfg.camera.index = camera
    kb = KnowledgeBase.load(cfg.path(cfg.guidance.knowledge_base))
    warnings += kb.warnings
    for w in warnings:
        print("warning:", w, file=sys.stderr)
    tutorials = TutorialService(cfg.tutorials, cfg.path(cfg.tutorials.cache_db))
    pipeline = Pipeline(cfg, source=video)

    app = QApplication(sys.argv[:1])
    win = MainWindow(cfg, kb, tutorials, pipeline, warnings)
    win.show()
    if autostart or video:
        win.start_camera()
    return app.exec()
