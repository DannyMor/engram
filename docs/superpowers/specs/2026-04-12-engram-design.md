# Engram — Design Spec

A persistent local service that acts as a self-curating memory system for coding preferences. It learns preferences passively during Claude Code sessions, stores them in a structured semantic store, deduplicates and resolves conflicts automatically, and injects relevant preferences into every new coding session — scoped to the language/framework in use.

---

## Problem

When working with Claude Code across many sessions, you repeatedly give the same feedback. Preferences drift, contradict each other, and never persist. There's no way to say "always do X in Python" and have that apply to every future session automatically.

---

## Architecture Overview

Single Python process running on localhost, always on via launchd. Serves three roles from one FastAPI application on port 3000:

1. **MCP endpoint** (`/mcp`) — Claude Code connects here via HTTP transport
2. **Web API** (`/api/...`) — backend for the web UI and injector hook
3. **Static UI** (`/`) — serves the single-file web UI

```
┌─────────────────────────────────────────────────┐
│              engram service (:3000)              │
│                                                 │
│   /        ←  web UI (Alpine.js + Tailwind)     │
│   /api/*   ←  REST API for UI + injector        │
│   /mcp     ←  MCP endpoint (FastMCP over HTTP)  │
│                                                 │
│   memory.py  ←→  Mem0                           │
│                    └── fastembed (local)         │
│                    └── embedded Qdrant           │
│                    └── Anthropic LLM             │
└─────────────────────────────────────────────────┘
        ▲                          ▲
        │                          │
  Claude Code CLI             browser
  (MCP + hook)            (always accessible)
```

---

## Project Structure

```
engram/
  src/
    engram/
      __init__.py
      server.py          ← FastAPI app: MCP + web API + static UI
      memory.py           ← Mem0 wrapper, preference schema, scoping
      curator.py          ← curation agent logic (Anthropic SDK)
      injector.py         ← generates CLAUDE.md preference block
      config.py           ← loads config.yaml + env vars
      models.py           ← Pydantic models for preferences, config, API
      logging.py          ← structured logger setup
  ui/
    index.html            ← single-file web UI (no build step)
  tests/
    conftest.py
    test_memory.py
    test_server.py
    test_curator.py
    test_injector.py
  config.yaml             ← default config (copied to ~/.engram/ on first run)
  justfile
  pyproject.toml
  .env.example
  README.md
```

---

## Tooling

| Tool | Purpose | Version |
|---|---|---|
| Python | Runtime | 3.14 |
| uv | Package management | latest |
| ruff | Linting + formatting | 0.15.10 |
| pyright | Type checking | 1.1.408 |
| pytest | Testing | 9.0.3 |
| just | Task runner | latest |

All tool configuration lives in `pyproject.toml`.

---

## Dependencies

### Runtime

| Package | Version | Purpose |
|---|---|---|
| mem0ai | 1.0.11 | Memory store with semantic dedup |
| fastapi | 0.135.3 | Web server + API |
| uvicorn | 0.44.0 | ASGI server |
| fastmcp | 3.2.3 | MCP server framework |
| anthropic | 0.94.0 | LLM calls (conflict resolution, curation agent) |
| pydantic | 2.12.5 | Data models and validation |
| qdrant-client | 1.17.1 | Embedded vector storage |
| fastembed | 0.8.0 | Local text embeddings |

### Dev

| Package | Version | Purpose |
|---|---|---|
| ruff | 0.15.10 | Linting + formatting |
| pyright | 1.1.408 | Type checking |
| pytest | 9.0.3 | Testing |

---

## Memory Layer

### Preference Model

```python
{
  "id": "uuid-from-mem0",
  "text": "Use pytest fixtures over setup/teardown methods. Prefer factory fixtures.",
  "scope": "python",
  "repo": null,                     # null = applies to all repos, or "engram", "vonnegut", etc.
  "tags": ["testing", "pytest"],
  "source": "coding-session",      # coding-session | curation-agent | manual
  "confidence": "high",            # high | low (low = flagged for review)
  "created_at": "2026-04-12T...",
  "updated_at": "2026-04-12T..."
}
```

Fields map to Mem0 as follows:
- `text` → Mem0's `memory` field
- `scope`, `repo`, `tags`, `source`, `confidence` → Mem0 `metadata` dict
- `id`, `created_at`, `updated_at` → Mem0 native fields

### Scoping

Two dimensions of scoping:

- **scope** — language/domain: `global`, `python`, `typescript`, `react`, `testing`, `git`, `documentation`, etc. A preference has one scope and zero or more tags.
- **repo** — optional repo name: `null` means the preference applies everywhere, a repo name (e.g., `"engram"`) means it only applies in that repo. This allows legitimately conflicting preferences across repos (e.g., "skip type annotations" in a legacy repo vs "strict type annotations required" in a new repo).

Scope is the primary filter for injection; repo narrows within that scope; tags are secondary for browsing and search.

### Memory Operations

| Operation | Behavior |
|---|---|
| `add(text, scope, repo?, tags?)` | Mem0 `add()` with metadata. Mem0 auto-deduplicates via LLM — updates/merges if a similar pref exists within the same repo context |
| `search(query, scope?, repo?)` | Semantic search via Mem0 `search()` with optional scope and repo filters |
| `get_all(scope?, repo?, tags?)` | List all prefs via Mem0 `get_all()` with metadata filters |
| `delete(id)` | Hard delete from Mem0 |
| `update(id, text?, scope?, repo?, tags?)` | Update existing preference in Mem0 |

### Conflict Handling

Mem0's `add()` auto-resolves duplicates and contradictions via LLM. Dedup comparison is scoped to the same repo — two preferences that contradict each other but target different repos are not treated as conflicts. When Mem0 updates or deletes an existing memory during an add, we log the event. If confidence in the resolution is uncertain, the preference is stored with `confidence: low` and surfaced in the UI for human review.

### Configuration

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY    # reads from environment first

embedder:
  provider: fastembed               # local, no API key needed
  model: BAAI/bge-small-en-v1.5    # ~50MB, downloads once

storage:
  path: ~/.engram/data              # embedded Qdrant writes here
```

The LLM API key is resolved in order: environment variable → `~/.engram/.env` → settings UI prompt.

---

## MCP Server

HTTP transport via FastMCP, served on the same FastAPI process at `/mcp`.

### Tools

| Tool | Purpose | Called by |
|---|---|---|
| `add_preference(text, scope, repo?, tags?)` | Store new preference, Mem0 handles dedup within repo context | Claude Code (passive capture) |
| `get_preferences_for_context(languages?, repo?)` | Get relevant prefs for a session, combining repo-specific + universal (repo=null) prefs | Injector hook |
| `search_preferences(query, scope?, repo?, tags?)` | Semantic search across prefs | Curation agent, Claude Code |
| `list_preferences(scope?, repo?, tags?)` | List all prefs with filters | Curation agent, web UI |
| `delete_preference(id)` | Hard delete | Curation agent, web UI |
| `update_preference(id, text?, scope?, repo?, tags?)` | Modify existing pref | Curation agent, web UI |

### MCP Server Description

The MCP server description instructs Claude Code to passively capture preferences:

> Engram is the user's coding preference memory. When the user gives feedback about how code should be written — coding style, patterns to use or avoid, testing approaches, naming conventions, architectural preferences — call add_preference() to store it. Examples: "don't mock the database in tests", "use frozen dataclasses", "prefer composition over inheritance". Do not store task-specific instructions or one-off corrections. At session start, preferences are already loaded into context via CLAUDE.md — do not call get_preferences_for_context() yourself.

---

## Session Injection

A Claude Code hook that fires at session start:

1. Detects file extensions in the project directory (`.py` → python, `.ts` → typescript, etc.)
2. Detects the repo name from `git remote` (same approach as `~/mydev/tools/github/gh_env.zsh`)
3. Calls `GET http://localhost:3000/api/inject?scopes=python,testing,global&repo=engram`
4. Returns repo-specific prefs + universal prefs (repo=null), merged and deduplicated
5. Writes the response into a managed block in the user-level `~/.claude/CLAUDE.md`:

```markdown
<!-- engram:start -->
## Coding Preferences (managed by engram)
- Use pytest fixtures over setup/teardown methods
- Prefer frozen dataclasses for value objects
- Don't mock the database in integration tests
<!-- engram:end -->
```

6. The block is **replaced** on every session start — it's a dynamic snapshot from the memory store, not persistent in the file

The hook is a shell script installed into Claude Code's settings. `just install-hook` sets it up, `just uninstall-hook` removes it.

**Graceful degradation:** If engram is not running, the hook silently skips injection. Claude Code works normally, just without preferences.

---

## Web UI

Single HTML file (`ui/index.html`) using Alpine.js + Tailwind CSS + Lucide Icons via CDN. No build step.

### Views

**Preferences (default):**
- Search bar with semantic search
- Scope/tag sidebar for filtering
- Preference cards: text, scope, tags, source, confidence badge
- Inline edit/delete
- "Low confidence" badge on prefs flagged for review
- Manual add preference button

**Chat (curation agent):**
- Chat panel for conversations with the curation agent
- Streaming responses
- Agent can add, update, delete, search preferences
- Example prompts: "clean up my Python prefs", "what conflicts exist?", "I'm starting a Go project, what should I add?"

**Settings:**
- LLM provider and model picker
- API key input
- Embedding provider picker (fastembed default)
- Test connection button
- Service health status

### Backend API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/preferences` | GET | List/search preferences (query, scope, tags params) |
| `/api/preferences` | POST | Add a preference manually |
| `/api/preferences/:id` | GET | Get single preference |
| `/api/preferences/:id` | PUT | Update preference |
| `/api/preferences/:id` | DELETE | Delete preference |
| `/api/scopes` | GET | List all scopes in use |
| `/api/tags` | GET | List all tags in use |
| `/api/chat` | POST | Send message to curation agent (streaming) |
| `/api/inject` | GET | Get formatted preferences for CLAUDE.md injection |
| `/api/config` | GET | Get current configuration |
| `/api/config` | PUT | Update configuration |
| `/api/health` | GET | Service health check |

---

## Curation Agent

System prompt loaded with all existing preferences as context. Uses the configured LLM with streaming via the Anthropic SDK (or configured provider). The agent can execute all memory operations — add, update, delete, search — through tool use.

The curation agent's focus is preference management, unlike the coding agent where preferences are a side effect. It handles:

- Bulk cleanup and deduplication review
- Proactive preference suggestions for new projects
- Conflict identification and resolution
- Preference summarization and analysis

---

## Service Lifecycle

### Background Service

macOS launchd plist at `~/Library/LaunchAgents/com.engram.service.plist`:
- Starts on login
- Restarts on crash
- Logs to `~/.engram/logs/`
- Runs `uv run python -m engram.server`

### Data Directory

```
~/.engram/
  data/           ← embedded Qdrant vector storage
  config.yaml     ← runtime config (copied from repo defaults on first run)
  .env            ← API key overrides (optional, env vars take precedence)
  logs/
    engram.log    ← service logs, rotated
```

### Justfile Commands

| Command | Purpose |
|---|---|
| `just dev` | Run in foreground with auto-reload |
| `just start` | Start background service via launchctl |
| `just stop` | Stop background service |
| `just restart` | Restart background service |
| `just status` | Check if service is running |
| `just logs` | Tail service logs |
| `just install` | Install launchd plist + Claude Code hook |
| `just uninstall` | Remove launchd plist + Claude Code hook |
| `just install-hook` | Install Claude Code session hook only |
| `just uninstall-hook` | Remove Claude Code session hook only |
| `just lint` | ruff check + ruff format --check |
| `just format` | ruff format |
| `just typecheck` | pyright |
| `just test` | pytest |
| `just check` | lint + typecheck + test |
| `just setup` | uv sync + first-time setup |
| `just push` | Push branch via ~/mydev/tools/github |
| `just pr` | Create PR via ~/mydev/tools/github |
| `just quick` | Create and merge PR via ~/mydev/tools/github |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Service not running | Claude Code hook silently skips injection. MCP shows as disconnected. Claude Code works normally. |
| No LLM configured | `add_preference()` falls back to `infer=False` (raw storage without dedup). Warning in settings UI. |
| No preferences yet | Injection returns empty block. UI shows empty state with suggested actions. |
| Scope detection fails | Hook falls back to `scope=global`, returns only global preferences. |
| Mem0 dedup uncertain | Preference stored with `confidence: low`, surfaced in UI for review. |

---

## Logging

Python `logging` module with structured format. Configurable log level via `config.yaml`. Key log points:

- Service start/stop
- MCP tool calls (tool name, scope, result count)
- Preference added/updated/deleted (with dedup action taken)
- Injection requests (scopes requested, prefs returned)
- Curation agent interactions
- LLM API call failures
- Configuration changes

No print statements. All output goes through the logger.

---

## Git Operations

All GitHub operations use `~/mydev/tools/github/` (DannyMor account). Token stored in macOS Keychain via `store_github_token engram <token>`. The justfile wraps `gpr`, `gquick`, and push commands for convenience.
