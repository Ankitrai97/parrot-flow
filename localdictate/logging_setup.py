from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os


def configure_logging() -> logging.Logger:
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LocalDictate" / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("localdictate")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        file_handler = RotatingFileHandler(directory / "localdictate.log", maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger
