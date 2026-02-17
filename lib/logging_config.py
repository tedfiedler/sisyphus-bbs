"""Logging configuration for the Sisyphus BBS application."""

import logging

from lib import config


def setup_logging():
    """Configure root logger with file and console handlers using a timestamped format."""
    log_file = config.LOG_DIR / "sisyphus.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler = logging.FileHandler(str(log_file))
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
