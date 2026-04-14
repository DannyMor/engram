"""Tests for main entry point dispatch."""

from unittest.mock import MagicMock, patch

from engram.main import main


def test_main_dispatches_to_stdio():
    with patch("engram.main.parse_args") as mock_parse, \
         patch("engram.main.run_stdio") as mock_stdio:
        mock_parse.return_value = MagicMock(command="stdio", config=None)
        main()
        mock_stdio.assert_called_once()


def test_main_dispatches_to_serve():
    with patch("engram.main.parse_args") as mock_parse, \
         patch("engram.main.run_serve") as mock_serve:
        mock_parse.return_value = MagicMock(command="serve", config=None, host=None, port=None)
        main()
        mock_serve.assert_called_once()


def test_main_dispatches_to_setup():
    with patch("engram.main.parse_args") as mock_parse, \
         patch("engram.main.run_setup") as mock_setup:
        mock_parse.return_value = MagicMock(command="setup", config=None)
        main()
        mock_setup.assert_called_once()


def test_main_custom_config_path(tmp_path):
    config_file = tmp_path / "custom.yaml"
    config_file.write_text("server:\n  port: 9999\n")

    with patch("engram.main.parse_args") as mock_parse, \
         patch("engram.main.run_serve") as mock_serve:
        mock_parse.return_value = MagicMock(
            command="serve", config=str(config_file), host=None, port=None
        )
        main()
        call_kwargs = mock_serve.call_args
        config = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1]["config"]
        assert config.server.port == 9999
