from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import TextIO

from .internal import normalize_logging_level

def configure_test_logging(  # pylint: disable=too-many-arguments
    log_path: str | Path,
    *,
    logger_name: str = "behave-tests",
    level: int | str = "INFO",
    console: bool = True,
    console_stream: TextIO | None = None,
    mode: str = "w",
) -> logging.Logger:
    """Configure a dedicated logger that writes to a file and, optionally, console."""

    resolved_path = Path(log_path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(normalize_logging_level(level))
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler(resolved_path, mode=mode, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(console_stream or sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
