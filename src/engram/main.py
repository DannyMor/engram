"""Entry point for engram — dispatches to stdio, serve, or setup mode."""

import os
import sys

import yaml

from engram.cli import parse_args
from engram.core.config import ENGRAM_HOME, load_config
from engram.core.logging import setup_logging
from engram.core.models import EngramConfig
from engram.setup import run_setup


def _load_config_from_path(path: str) -> EngramConfig:
    """Load config from an explicit file path."""
    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Error: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in {path}: {e}", file=sys.stderr)
        sys.exit(1)
    return EngramConfig(**raw)


def run_stdio(config: EngramConfig) -> None:
    """Run engram as a stdio MCP server for Claude Code."""
    log_dir = ENGRAM_HOME / "logs"
    setup_logging(level=config.logging.level, stdio_mode=True, log_dir=log_dir)

    from engram.mcp import create_mcp
    from engram.storage.mem0 import Mem0PreferenceStore

    store = Mem0PreferenceStore(config)
    mcp = create_mcp(store)
    mcp.run(transport="stdio", show_banner=False)


def run_serve(config: EngramConfig, host: str | None = None, port: int | None = None) -> None:
    """Run engram as an HTTP server with web UI."""
    import uvicorn

    from engram.app import create_app

    effective_host = host or os.environ.get("ENGRAM_HOST") or config.server.host
    effective_port = port or int(os.environ.get("ENGRAM_PORT", "0")) or config.server.port

    setup_logging(level=config.logging.level, stdio_mode=False, log_dir=ENGRAM_HOME / "logs")
    app = create_app(config=config)

    try:
        uvicorn.run(app, host=effective_host, port=effective_port)
    except OSError as e:
        if "address already in use" in str(e).lower() or getattr(e, "errno", 0) == 98:
            print(
                f"Error: Port {effective_port} is already in use.\n"
                f"Set a different port with --port or in ~/.engram/config.yaml",
                file=sys.stderr,
            )
            sys.exit(1)
        raise


def main() -> None:
    """Parse CLI args and dispatch to the appropriate mode."""
    args = parse_args()

    match args.command:
        case "setup":
            run_setup()
        case "serve":
            config = _load_config_from_path(args.config) if args.config else load_config()
            run_serve(config, host=args.host, port=args.port)
        case "stdio":
            config = _load_config_from_path(args.config) if args.config else load_config()
            run_stdio(config)
        case _:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
