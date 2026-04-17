"""CLI argument parser for engram."""

import argparse


def _valid_port(value: str) -> int:
    port = int(value)
    if not (1 <= port <= 65535):
        raise argparse.ArgumentTypeError(f"port must be 1-65535, got {port}")
    return port


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Commands:
        (none)  — stdio MCP server (default, for Claude Code)
        serve   — HTTP server with web UI
        setup   — first-run setup
    """
    parser = argparse.ArgumentParser(
        prog="engramd",
        description="Self-consolidating coding imprint memory for Claude Code",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="path to config YAML file",
    )
    parser.set_defaults(host=None, port=None)

    subparsers = parser.add_subparsers(dest="command")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="run HTTP server with web UI")
    serve_parser.add_argument(
        "--host",
        default=None,
        help="host to bind to (overrides config)",
    )
    serve_parser.add_argument(
        "--port",
        type=_valid_port,
        default=None,
        help="port to bind to (overrides config)",
    )

    # setup subcommand
    subparsers.add_parser("setup", help="first-run setup: config, model download, validation")

    args = parser.parse_args(argv)

    # Default to stdio when no subcommand given
    if args.command is None:
        args.command = "stdio"

    return args
