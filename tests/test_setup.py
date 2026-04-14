"""Tests for the setup command."""

import os
from unittest.mock import patch

from engram.setup import run_setup


def _patch_home(tmp_path):
    """Patch ENGRAM_HOME and USER_CONFIG_PATH in both setup and config modules."""
    home = tmp_path / ".engram"
    config_path = home / "config.yaml"
    return (
        patch("engram.setup.ENGRAM_HOME", home),
        patch("engram.setup.USER_CONFIG_PATH", config_path),
        patch("engram.core.config.ENGRAM_HOME", home),
        patch("engram.core.config.USER_CONFIG_PATH", config_path),
        home,
        config_path,
    )


def test_setup_creates_config_directory(tmp_path):
    p_home, p_ucp, p_cfg_home, p_cfg_ucp, home, _ = _patch_home(tmp_path)
    with p_home, p_ucp, p_cfg_home, p_cfg_ucp:
        run_setup(skip_model_download=True)

    assert home.exists()
    assert (home / "data").exists()
    assert (home / "logs").exists()


def test_setup_creates_default_config(tmp_path):
    p_home, p_ucp, p_cfg_home, p_cfg_ucp, _, config_path = _patch_home(tmp_path)
    with p_home, p_ucp, p_cfg_home, p_cfg_ucp:
        run_setup(skip_model_download=True)

    assert config_path.exists()
    content = config_path.read_text()
    assert "3777" in content


def test_setup_does_not_overwrite_existing_config(tmp_path):
    p_home, p_ucp, p_cfg_home, p_cfg_ucp, home, config_path = _patch_home(tmp_path)
    home.mkdir()
    config_path.write_text("custom: true\n")

    with p_home, p_ucp, p_cfg_home, p_cfg_ucp:
        run_setup(skip_model_download=True)

    assert config_path.read_text() == "custom: true\n"


def test_setup_reports_api_key_status(tmp_path, capsys):
    p_home, p_ucp, p_cfg_home, p_cfg_ucp, _, _ = _patch_home(tmp_path)
    with p_home, p_ucp, p_cfg_home, p_cfg_ucp, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=False):
        run_setup(skip_model_download=True)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "ANTHROPIC_API_KEY" in combined
