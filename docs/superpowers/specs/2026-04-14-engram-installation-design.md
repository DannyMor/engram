# Engram Installation & Distribution Design

## Goal

Make engram installable via `uvx engram` / `pip install engram` with two modes: stdio (for Claude Code integration) and HTTP (for web UI + REST API). Follow-up: wrap as a Claude Code plugin.

## Architecture

Engram is a single Python package published to PyPI. It exposes one CLI entry point (`engram`) that dispatches to two modes based on subcommand:

- **stdio mode** (`engram`, no args) — MCP server over stdin/stdout. Claude Code spawns and manages the process. No HTTP server, no web UI.
- **serve mode** (`engram serve`) — Full HTTP server with FastAPI + MCP endpoint + REST API + web UI on configurable port (default 3777).
- **setup command** (`engram setup`) — One-time first-run setup: creates config, downloads embedder model, validates environment.

Both modes share the same `PreferenceStore`, config loading, MCP tool definitions, and data directory (`~/.engram/data/`). The only difference is the transport layer.

## CLI Design

```
engram              # stdio MCP server (default, for Claude Code)
engram serve        # HTTP server with web UI
engram setup        # first-run setup
engram serve --port 4000 --host 127.0.0.1   # override defaults
engram --config /path/to/config.yaml         # custom config
ENGRAM_PORT=4000 engram serve                # env var override
```

Argument parsing via `argparse`. No heavy CLI framework.

Entry point in pyproject.toml: `engram = "engram.main:main"`

## Stdio Mode

The stdio entry point:

1. Loads config (`~/.engram/config.yaml`, creates defaults if missing)
2. Initializes `Mem0PreferenceStore` (embedded Qdrant + fastembed)
3. Runs FastMCP server with `transport="stdio"`

**Critical constraint: stdout must be clean.** All logging in stdio mode goes to stderr or file (`~/.engram/logs/engram.log`), never stdout. Any non-JSON-RPC output on stdout breaks the protocol.

The fastembed model download (~100MB) on first run logs progress to stderr. Claude Code surfaces stderr as diagnostics.

## Serve Mode

Identical to what exists today, with port changed to 3777:

- FastAPI app with MCP mounted at `/mcp`
- REST API at `/api/*`
- Web UI served at `/`
- Port conflict: fail with clear error message suggesting `--port` or config change. No auto-port-hopping.

## First-Run Experience

### Quick path (two commands):

```bash
engram setup                          # config + model download
claude mcp add engram -- uvx engram   # register with Claude Code
```

### What `engram setup` does:

1. Creates `~/.engram/` directory structure (`data/`, `logs/`)
2. Writes default `~/.engram/config.yaml` if not present
3. Downloads fastembed model (with progress bar on stderr)
4. Validates `ANTHROPIC_API_KEY` if set (non-blocking — CRUD works without it)
5. Prints next steps

### Without setup (still works):

Running `engram` or `engram serve` without prior setup auto-creates config and directories. The model downloads on first query. `engram setup` is a convenience, not a requirement.

## PyPI Publishing

- **Package name**: `engram` (fallback: `engram-mcp` if taken)
- **Build system**: hatchling (existing)
- **Python version**: `requires-python = ">=3.11"` (lowered from 3.14)
  - Code uses match statements (3.10+), union syntax (3.10+), generic builtins (3.9+)
  - Develop on 3.14, CI tests on 3.11, 3.12, 3.13, 3.14
- **Publishing**: `uv build && uv publish`, or GitHub Actions on tag push

## Default Port

Port 3777 (uncommon, not in well-known service registries). Configurable via:
- `--port` CLI flag
- `server.port` in `~/.engram/config.yaml`
- `ENGRAM_PORT` environment variable

On conflict: clear error message, no auto-hopping.

## Codebase Changes

### New files:
- `src/engram/cli.py` — argparse definition
- `src/engram/setup.py` — `engram setup` command logic

### Modified files:
- `src/engram/main.py` — dispatch between stdio/serve/setup
- `src/engram/mcp/server.py` — add function to run in stdio mode
- `src/engram/core/logging.py` — mode-aware logging (stderr/file for stdio, stdout for serve)
- `pyproject.toml` — `requires-python >= 3.11`, default port 3777
- `config.yaml` — default port 3777

### Untouched:
- `PreferenceStore`, `Mem0PreferenceStore`
- MCP tool definitions
- REST API routes
- Web UI
- `app.py` (app factory, used only by serve mode)
- LLM clients, curator agent

## Future: Claude Code Plugin (Approach B)

After A ships, wrap engram as a Claude Code plugin:

```
engram-plugin/
├── plugin.json         # manifest
├── .mcp.json           # stdio server config
├── skills/             # optional slash commands
└── hooks/              # optional session hooks
```

The plugin's `.mcp.json` simply invokes `uvx engram`. Plugin installation: `claude plugin install engram@marketplace`. This is a packaging exercise — no core code changes needed.

## Concurrent Access

For v1: stdio mode and serve mode should not run simultaneously against the same data directory. Embedded Qdrant doesn't support multi-process access. Document this limitation. Future options: file locking, or having stdio mode proxy through the HTTP server if it's running.
