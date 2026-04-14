"""Tests for mode-aware logging setup."""

import logging

from engram.core.logging import setup_logging


def test_setup_logging_stdio_uses_stderr(capsys, tmp_path):
    """In stdio mode, console handler writes to stderr, not stdout."""
    setup_logging(level="INFO", stdio_mode=True, log_dir=tmp_path)
    logger = logging.getLogger("test_stdio")
    logger.info("stdio test message")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "stdio test message" in captured.err


def test_setup_logging_serve_uses_stdout(capsys, tmp_path):
    """In serve mode, console handler writes to stdout."""
    setup_logging(level="INFO", stdio_mode=False, log_dir=tmp_path)
    logger = logging.getLogger("test_serve")
    logger.info("serve test message")

    captured = capsys.readouterr()
    assert "serve test message" in captured.out


def test_setup_logging_creates_log_file(tmp_path):
    """Log file is created when log_dir is provided."""
    setup_logging(level="INFO", log_dir=tmp_path)
    logger = logging.getLogger("test_file")
    logger.info("file test message")

    log_file = tmp_path / "engram.log"
    assert log_file.exists()
    assert "file test message" in log_file.read_text()
