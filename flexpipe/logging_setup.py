"""
Structured logging configuration for flexpipe.

All modules use ``logging.getLogger(__name__)``; this module wires up the
root logger with a consistent format that works both interactively and in
scheduled/service runs (where output is captured to per-build log files).

Usage::

    from flexpipe.logging_setup import configure_logging
    configure_logging(level="INFO", log_file="/path/to/run.log")

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting fetch")
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def configure_logging(
    level: Union[str, int] = "INFO",
    log_file: Optional[Union[str, Path]] = None,
    force: bool = False,
) -> None:
    """Configure the root logger for flexpipe.

    Args:
        level: Logging level (e.g. ``"DEBUG"``, ``"INFO"``, ``"WARNING"``).
            Also accepts integer constants from the ``logging`` module.
        log_file: Optional path to a file for log output. When given, logs are
            written to both stderr and the file.
        force: Passed to ``logging.basicConfig``; re-configures even if
            handlers are already attached (useful in tests).
    """
    handlers: list = [logging.StreamHandler(sys.stderr)]

    if log_file is not None:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(file_path), encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=handlers,
        force=force,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger.

    Convenience wrapper so modules can do::

        from flexpipe.logging_setup import get_logger
        logger = get_logger(__name__)

    instead of importing the ``logging`` module directly.
    """
    return logging.getLogger(name)
