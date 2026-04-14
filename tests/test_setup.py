"""Tests for the setup command."""

import os
from unittest.mock import patch

from engram.setup import run_setup


def test_setup_creates_config_directory(tmp_path):
    home = tmp_path / ".engram"
    with patch("engram.setup.ENGRAM_HOME", home):
        run_setup(skip_model_download=True)

    assert home.exists()
    assert (home / "data").exists()
    assert (home / "logs").exists()


def test_setup_creates_default_config(tmp_path):
    home = tmp_path / ".engram"
    with patch("engram.setup.ENGRAM_HOME", home), \
         patch("engram.setup.USER_CONFIG_PATH", home / "config.yaml"):
        run_setup(skip_model_download=True)

    config_path = home / "config.yaml"
    assert config_path.exists()
    content = config_path.read_text()
    assert "3777" in content


def test_setup_does_not_overwrite_existing_config(tmp_path):
    home = tmp_path / ".engram"
    home.mkdir()
    config_path = home / "config.yaml"
    config_path.write_text("custom: true\n")

    with patch("engram.setup.ENGRAM_HOME", home), \
         patch("engram.setup.USER_CONFIG_PATH", config_path):
        run_setup(skip_model_download=True)

    assert config_path.read_text() == "custom: true\n"


def test_setup_reports_api_key_status(tmp_path, capsys):
    home = tmp_path / ".engram"
    with patch("engram.setup.ENGRAM_HOME", home), \
         patch("engram.setup.USER_CONFIG_PATH", home / "config.yaml"), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=False):
        run_setup(skip_model_download=True)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "ANTHROPIC_API_KEY" in combined
