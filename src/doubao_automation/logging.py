from __future__ import annotations

import logging
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
APP_LOG_PATH = RUNTIME_DIR / "app.log"


def configure_logging(level: str) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    if getattr(root_logger, "_doubao_configured", False):
        root_logger.setLevel(getattr(logging, level, logging.INFO))
        return

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(APP_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    root_logger._doubao_configured = True  # type: ignore[attr-defined]


def get_app_log_path() -> Path:
    return APP_LOG_PATH
