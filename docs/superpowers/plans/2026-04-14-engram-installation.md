# Engram Installation & Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make engram installable via `uvx engram-ai` with stdio MCP transport for Claude Code, plus an HTTP serve mode for the web UI, and publish to PyPI.

**Architecture:** Add argparse-based CLI dispatching to the existing entry point. Stdio mode runs FastMCP over stdin/stdout. Serve mode runs the existing FastAPI app. A setup command handles first-run initialization. Logging is mode-aware (stderr for stdio, stdout for serve).

**Tech Stack:** Python 3.11+, FastMCP (stdio + http), argparse, fastembed, hatchling (PyPI build)

**PyPI name:** `engram` is taken (placeholder), `engram-mcp` is taken (different project). Available options: `engram-ai`, `engram-prefs`. The plan uses `engram-ai` — change in pyproject.toml if a different name is chosen.

---

### Task 1: Update pyproject.toml for PyPI publishing

**Files:**
- Modify: `pyproject.toml`

This task lowers the Python version requirement, updates the default port, adds PyPI classifiers, and ensures the package is ready for publishing. No code logic changes.

- [ ] **Step 1: Update pyproject.toml**

```toml
[project]
name = "engram-ai"
version = "0.1.0"
description = "Self-curating coding preference memory for Claude Code"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [{ name = "DannyMor" }]
keywords = ["claude", "mcp", "preferences", "coding", "memory"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "mem0ai==1.0.11",
    "fastapi==0.135.3",
    "uvicorn==0.44.0",
    "fastmcp==3.2.3",
    "anthropic==0.94.0",
    "pydantic==2.12.5",
    "qdrant-client==1.17.1",
    "fastembed==0.8.0",
    "pyyaml>=6.0",
    "boto3>=1.42.88",
]

[project.optional-dependencies]
dev = [
    "ruff==0.15.10",
    "pyright==1.1.408",
    "pytest==9.0.3",
    "pytest-asyncio>=1.0",
    "httpx>=0.28",
]

[project.urls]
Homepage = "https://github.com/DannyMor/engram"
Repository = "https://github.com/DannyMor/engram"

[project.scripts]
engram = "engram.main:main"

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.pyright]
venvPath = "."
venv = ".venv"
pythonVersion = "3.11"
typeCheckingMode = "standard"
include = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/engram"]
```

- [ ] **Step 2: Update default port in config.yaml**

Change the repo-level default config:

```yaml
server:
  host: "0.0.0.0"
  port: 3777

llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY

embedder:
  provider: fastembed
  model: BAAI/bge-small-en-v1.5

storage:
  path: ~/.engram/data

logging:
  level: INFO
```

- [ ] **Step 3: Update ServerConfig default port in models.py**

In `src/engram/core/models.py`, change the `ServerConfig` default:

```python
class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 3777
```

- [ ] **Step 4: Run uv sync to verify dependency resolution**

Run: `uv sync --all-extras`
Expected: Resolves successfully with no errors.

- [ ] **Step 5: Run existing tests**

Run: `uv run pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All existing tests PASS. The port change doesn't affect tests since they use `EngramConfig()` defaults.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml config.yaml src/engram/core/models.py
git commit -m "chore: prepare pyproject.toml for PyPI publishing and update default port to 3777"
```

---

### Task 2: Mode-aware logging (stderr for stdio, stdout for serve)

**Files:**
- Modify: `src/engram/core/logging.py`
- Create: `tests/test_logging.py`

Stdio mode must never write to stdout — all logging goes to stderr and/or a log file. Serve mode keeps the current stdout behavior.

- [ ] **Step 1: Write the failing test**

Create `tests/test_logging.py`:

```python
"""Tests for mode-aware logging setup."""

import logging
import sys

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_logging.py -v`
Expected: FAIL — `setup_logging()` doesn't accept `stdio_mode` parameter yet.

- [ ] **Step 3: Implement mode-aware logging**

Replace `src/engram/core/logging.py`:

```python
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

    # Clear any existing handlers to avoid duplicates
    root = logging.getLogger()
    root.handlers.clear()

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_logging.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All tests PASS. Existing callers pass `setup_logging("INFO")` which still works (new params have defaults).

- [ ] **Step 6: Commit**

```bash
git add src/engram/core/logging.py tests/test_logging.py
git commit -m "feat: mode-aware logging — stderr for stdio, stdout for serve"
```

---

### Task 3: CLI argument parser

**Files:**
- Create: `src/engram/cli.py`
- Create: `tests/test_cli.py`

Define the argparse interface: default command (stdio), `serve` subcommand, `setup` subcommand, and shared flags.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
"""Tests for CLI argument parsing."""

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `engram.cli` module doesn't exist.

- [ ] **Step 3: Implement the argument parser**

Create `src/engram/cli.py`:

```python
"""CLI argument parser for engram."""

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Commands:
        (none)  — stdio MCP server (default, for Claude Code)
        serve   — HTTP server with web UI
        setup   — first-run setup
    """
    parser = argparse.ArgumentParser(
        prog="engram",
        description="Self-curating coding preference memory for Claude Code",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="path to config YAML file",
    )

    subparsers = parser.add_subparsers(dest="command")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="run HTTP server with web UI")
    serve_parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="host to bind to (overrides config)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engram/cli.py tests/test_cli.py
git commit -m "feat: CLI argument parser with stdio, serve, and setup commands"
```

---

### Task 4: Setup command

**Files:**
- Create: `src/engram/setup.py`
- Create: `tests/test_setup.py`

The `engram setup` command creates config, downloads the fastembed model, and validates the environment.

- [ ] **Step 1: Write the failing test**

Create `tests/test_setup.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL — `engram.setup` module doesn't exist.

- [ ] **Step 3: Implement the setup command**

Create `src/engram/setup.py`:

```python
"""First-run setup for engram: config, model download, environment validation."""

import os
import sys

import yaml

from engram.core.config import ENGRAM_HOME, USER_CONFIG_PATH
from engram.core.models import EngramConfig


def run_setup(skip_model_download: bool = False) -> None:
    """Run first-time setup for engram."""
    _print("Setting up engram...\n")

    # 1. Create directory structure
    ENGRAM_HOME.mkdir(parents=True, exist_ok=True)
    (ENGRAM_HOME / "data").mkdir(exist_ok=True)
    (ENGRAM_HOME / "logs").mkdir(exist_ok=True)
    _print(f"  Created {ENGRAM_HOME}/")

    # 2. Create default config if not present
    if not USER_CONFIG_PATH.exists():
        config = EngramConfig()
        data = config.model_dump()
        with open(USER_CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        _print(f"  Created {USER_CONFIG_PATH}")
    else:
        _print(f"  Config already exists at {USER_CONFIG_PATH}")

    # 3. Download fastembed model
    if not skip_model_download:
        _print("\n  Downloading embedding model (first time only)...")
        try:
            from fastembed import TextEmbedding

            TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            _print("  Model downloaded successfully.")
        except Exception as e:
            _print(f"  Warning: Could not download model: {e}")

    # 4. Check API key
    _print("")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        _print("  ANTHROPIC_API_KEY is set.")
    else:
        _print("  ANTHROPIC_API_KEY is not set.")
        _print("  (Optional — needed for curation agent. Basic CRUD works without it.)")

    # 5. Print next steps
    _print("\nSetup complete! Next steps:\n")
    _print("  # Register with Claude Code:")
    _print("  claude mcp add engram -- uvx engram-ai\n")
    _print("  # Or start the web UI:")
    _print("  engram serve\n")


def _print(msg: str) -> None:
    """Print to stderr (safe in all modes)."""
    print(msg, file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_setup.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/engram/setup.py tests/test_setup.py
git commit -m "feat: engram setup command for first-run initialization"
```

---

### Task 5: Wire up main.py to dispatch between modes

**Files:**
- Modify: `src/engram/main.py`
- Create: `tests/test_main.py`

The entry point now parses CLI args and dispatches to stdio, serve, or setup. This is the integration point.

- [ ] **Step 1: Write the failing test**

Create `tests/test_main.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — `main()` doesn't accept args or dispatch to modes yet.

- [ ] **Step 3: Implement main dispatch**

Replace `src/engram/main.py`:

```python
"""Entry point for engram — dispatches to stdio, serve, or setup mode."""

import os
import sys
from pathlib import Path

import yaml

from engram.cli import parse_args
from engram.core.config import ENGRAM_HOME, load_config
from engram.core.logging import setup_logging
from engram.core.models import EngramConfig
from engram.setup import run_setup


def _load_config_from_path(path: str) -> EngramConfig:
    """Load config from an explicit file path."""
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
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


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/engram/main.py tests/test_main.py
git commit -m "feat: main entry point dispatches to stdio, serve, and setup modes"
```

---

### Task 6: Verify stdio mode works end-to-end

**Files:**
- No new files — this is a manual verification task.

- [ ] **Step 1: Test stdio mode starts and responds to MCP initialize**

Run:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}' | uv run engram 2>/dev/null
```

Expected: A JSON-RPC response on stdout with `"result"` containing server capabilities. Stderr should have log output (not visible due to `2>/dev/null`).

- [ ] **Step 2: Verify nothing leaks to stdout except JSON-RPC**

Run:
```bash
echo '{}' | uv run engram 2>/tmp/engram-stderr.log | python3 -c "import sys; data = sys.stdin.read(); print('STDOUT bytes:', len(data)); print(repr(data[:200]))"
```

Expected: Only valid JSON-RPC content on stdout. Check `/tmp/engram-stderr.log` for log lines.

- [ ] **Step 3: Test serve mode starts on port 3777**

Run:
```bash
uv run engram serve &
sleep 3
curl -s http://localhost:3777/api/health | python3 -m json.tool
kill %1
```

Expected: `{"status": "ok"}` response from the health endpoint.

- [ ] **Step 4: Test serve mode port conflict error**

Run:
```bash
# Start a dummy listener on 3777
python3 -c "import socket; s=socket.socket(); s.bind(('',3777)); s.listen(); input()" &
DUMMY_PID=$!
uv run engram serve 2>&1
kill $DUMMY_PID
```

Expected: Clear error message on stderr: `Error: Port 3777 is already in use.`

- [ ] **Step 5: Test setup command**

Run:
```bash
uv run engram setup
```

Expected: Prints setup progress to stderr, creates `~/.engram/config.yaml` if not present, downloads model, shows next steps.

- [ ] **Step 6: Commit any fixes discovered during verification**

```bash
git add -u
git commit -m "fix: adjustments from end-to-end verification"
```

---

### Task 7: Build and verify PyPI package

**Files:**
- No new files — verification and publishing preparation.

- [ ] **Step 1: Build the package**

Run:
```bash
uv build
```

Expected: Creates `dist/engram_ai-0.1.0-py3-none-any.whl` and `dist/engram_ai-0.1.0.tar.gz`.

- [ ] **Step 2: Verify the wheel contains all files**

Run:
```bash
python3 -m zipfile -l dist/engram_ai-0.1.0-py3-none-any.whl | grep -E "\.py$|\.html$|\.yaml$"
```

Expected: Lists all source files under `engram/`, including `engram/ui/index.html` and `engram/main.py`.

- [ ] **Step 3: Test install in a clean environment**

Run:
```bash
uv venv /tmp/engram-test-env && source /tmp/engram-test-env/bin/activate
uv pip install dist/engram_ai-0.1.0-py3-none-any.whl
engram --help
engram setup --help 2>&1 || true
deactivate
rm -rf /tmp/engram-test-env
```

Expected: `engram --help` shows the CLI help with `serve` and `setup` subcommands.

- [ ] **Step 4: Test uvx execution**

Run:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}' | uvx --from ./dist/engram_ai-0.1.0-py3-none-any.whl engram 2>/dev/null
```

Expected: JSON-RPC initialize response on stdout.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "chore: verify PyPI package build and installation"
```

---

### Task 8: Include static assets in the wheel

**Files:**
- Modify: `pyproject.toml` (if needed)

The web UI (`src/engram/ui/index.html`) and default config (`config.yaml`) must be included in the wheel so `engram serve` works after `pip install`.

- [ ] **Step 1: Verify static files are included**

Run:
```bash
uv build && python3 -m zipfile -l dist/engram_ai-0.1.0-py3-none-any.whl | grep -E "index.html|config.yaml"
```

If `index.html` is listed under `engram/ui/index.html`, the hatchling config already handles it (since `packages = ["src/engram"]` includes all subdirectories). If `config.yaml` (the repo-level default) is NOT listed, we need to either:
- Bundle it inside `src/engram/` so it ships with the wheel, OR
- Rely on `EngramConfig()` defaults (which already produce the same values)

The `config.yaml` at the repo root is only used for `REPO_CONFIG_PATH` fallback during development. After PyPI install, `REPO_CONFIG_PATH` won't exist. But `load_config()` already handles this — it falls back to `EngramConfig()` defaults. So no change is needed for config.

- [ ] **Step 2: Update REPO_CONFIG_PATH to be resilient**

The current `REPO_CONFIG_PATH` uses `Path(__file__).parent.parent.parent.parent / "config.yaml"` which traverses up to the repo root. After pip install, this path doesn't exist, but `load_config()` already handles the missing file case gracefully. Verify:

Run:
```bash
uv venv /tmp/engram-config-test && source /tmp/engram-config-test/bin/activate
uv pip install dist/engram_ai-0.1.0-py3-none-any.whl
python3 -c "from engram.core.config import load_config; c = load_config(); print(c.server.port)"
deactivate
rm -rf /tmp/engram-config-test
```

Expected: Prints `3777` (from `EngramConfig()` defaults). No error about missing repo config.

- [ ] **Step 3: Commit if any changes were needed**

```bash
git add -u
git commit -m "fix: ensure static assets and config work in installed package"
```
