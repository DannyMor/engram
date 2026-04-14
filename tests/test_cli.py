"""Tests for CLI argument parsing."""

import pytest

from engram.cli import parse_args


def test_no_args_defaults_to_stdio():
    args = parse_args([])
    assert args.command == "stdio"


def test_serve_command():
    args = parse_args(["serve"])
    assert args.command == "serve"


def test_serve_custom_port():
    args = parse_args(["serve", "--port", "4000"])
    assert args.command == "serve"
    assert args.port == 4000


def test_serve_custom_host():
    args = parse_args(["serve", "--host", "127.0.0.1"])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"


def test_setup_command():
    args = parse_args(["setup"])
    assert args.command == "setup"


def test_global_config_flag():
    args = parse_args(["--config", "/tmp/test.yaml", "serve"])
    assert args.config == "/tmp/test.yaml"
    assert args.command == "serve"


def test_global_config_flag_with_stdio():
    args = parse_args(["--config", "/tmp/test.yaml"])
    assert args.config == "/tmp/test.yaml"
    assert args.command == "stdio"


def test_serve_invalid_port_rejected():
    with pytest.raises(SystemExit):
        parse_args(["serve", "--port", "0"])


def test_setup_has_default_host_port():
    args = parse_args(["setup"])
    assert args.host is None
    assert args.port is None
