"""
Daily logs via TimedRotatingFileHandler (midnight).
Log: status transitions (UP->DOWN, DOWN->UP), ping results, errors, app start/stop, config changes.
"""
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from core.config import get_config_dir


def setup_logging(log_path: str | None = None) -> logging.Logger:
    """
    Configure root logger with daily rotating file and console.
    Returns the app logger (e.g. 'pingu').
    """
    if log_path:
        log_dir = Path(log_path)
    else:
        log_dir = get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pingu.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    fh = TimedRotatingFileHandler(log_file, when="midnight", backupCount=30, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    logger = logging.getLogger("pingu")
    logger.setLevel(logging.DEBUG)
    return logger
