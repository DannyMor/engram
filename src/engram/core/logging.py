"""Structured logging setup for engram."""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    stdio_mode: bool = False,
    log_dir: Path | None = None,
) -> None:
    """Configure logging with mode-aware console output.

    In stdio mode, console logs go to stderr (stdout is reserved for JSON-RPC).
    In serve mode, console logs go to stdout (standard behavior).
    """
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    stream = sys.stderr if stdio_mode else sys.stdout
    handlers: list[logging.Handler] = [logging.StreamHandler(stream)]

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "engram.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
        )
        file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,
    )
