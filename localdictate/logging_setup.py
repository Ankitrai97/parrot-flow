from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import sys


def configure_logging() -> logging.Logger:
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ParrotFlow" / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("localdictate")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        file_handler = RotatingFileHandler(directory / "parrot-flow.log", maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        # pythonw and PyInstaller --windowed have no console streams.
        if sys.stderr is not None:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        logger.propagate = False
    return logger
