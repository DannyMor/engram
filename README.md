# Engram

Self-curating coding preference memory for Claude Code.

Engram learns your coding preferences passively during Claude Code sessions, stores them with semantic deduplication, and automatically injects relevant preferences into future sessions — scoped to the language, framework, and repository you're working in.

## Quick Start

```bash
# Install dependencies
just setup

# Start development server
just dev

# Open the web UI
open http://localhost:3777
```

## How It Works

1. **During coding sessions** — when you give feedback like "don't mock the database" or "use frozen dataclasses", Claude Code stores it via the engram MCP server
2. **Between sessions** — engram deduplicates, resolves conflicts, and organizes preferences using semantic search and LLM-driven analysis
3. **At session start** — a Claude Code hook injects relevant preferences into your CLAUDE.md, scoped to the project's languages and repo

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/)
- An Anthropic API key (set as `ANTHROPIC_API_KEY` environment variable)

### Installation

```bash
git clone https://github.com/DannyMor/engram.git
cd engram
just setup

# Install as background service + Claude Code hook
just install
```

### Claude Code MCP Configuration

Add to your Claude Code settings:

```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:3777/mcp"
    }
  }
}
```

## Commands

| Command | Purpose |
|---|---|
| `just dev` | Run in foreground with auto-reload |
| `just start` / `just stop` | Manage background service |
| `just status` | Check if service is running |
| `just logs` | Tail service logs |
| `just install` / `just uninstall` | Install/remove service + hook |
| `just check` | Run lint + typecheck + tests |

## Configuration

Configuration lives at `~/.engram/config.yaml`. Editable via the web UI settings page or directly.

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY

embedder:
  provider: fastembed
  model: BAAI/bge-small-en-v1.5

storage:
  path: ~/.engram/data
```

## Web UI

Open `http://localhost:3777` to:

- **Browse** preferences with search, scope filtering, and tag filtering
- **Chat** with the curation agent for bulk cleanup, conflict review, and proactive suggestions
- **Configure** LLM provider and model settings

## Architecture

Single Python process serving:
- MCP endpoint at `/mcp` (HTTP transport for Claude Code)
- REST API at `/api/*` (backend for web UI and injection hook)
- Static web UI at `/` (Alpine.js + Tailwind CSS)

Memory backend: Mem0 with embedded Qdrant (local vector storage) and fastembed (local embeddings).

## Development

```bash
just dev        # Start dev server with auto-reload
just test       # Run tests
just lint       # Run ruff
just typecheck  # Run pyright
just check      # All three
```
