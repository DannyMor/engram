# Engram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent local service that learns coding preferences from Claude Code sessions, stores them with semantic dedup, and injects relevant preferences into future sessions.

**Architecture:** Single FastAPI process on port 3000 serving MCP endpoint, REST API, and static web UI. Mem0 with embedded Qdrant handles vector storage and LLM-driven deduplication. fastembed provides local embeddings. A Claude Code hook injects preferences into CLAUDE.md at session start.

**Tech Stack:** Python 3.14, FastAPI, FastMCP, Mem0, Qdrant (embedded), fastembed, Anthropic SDK, Alpine.js, Tailwind CSS, uv, ruff, pyright, pytest, just, launchd

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/engram/__init__.py`
- Create: `src/engram/logging.py`
- Create: `src/engram/config.py`
- Create: `src/engram/models.py`
- Create: `config.yaml`
- Create: `.env.example`
- Create: `justfile`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "engram"
version = "0.1.0"
description = "Self-curating coding preference memory for Claude Code"
requires-python = ">=3.14"
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
]

[project.optional-dependencies]
dev = [
    "ruff==0.15.10",
    "pyright==1.1.408",
    "pytest==9.0.3",
    "pytest-asyncio>=1.0",
    "httpx>=0.28",
]

[tool.ruff]
target-version = "py314"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.pyright]
venvPath = "."
venv = ".venv"
pythonVersion = "3.14"
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

- [ ] **Step 2: Create default config.yaml**

```yaml
server:
  host: "0.0.0.0"
  port: 3000

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

- [ ] **Step 3: Create .env.example**

```
# Anthropic API key (optional if already set in shell environment)
# ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 4: Create src/engram/__init__.py**

```python
"""Engram — self-curating coding preference memory for Claude Code."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create src/engram/models.py**

All Pydantic models used throughout the project.

```python
"""Pydantic models for preferences, configuration, and API contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Source(StrEnum):
    CODING_SESSION = "coding-session"
    CURATION_AGENT = "curation-agent"
    MANUAL = "manual"


class Confidence(StrEnum):
    HIGH = "high"
    LOW = "low"


class Preference(BaseModel):
    id: str
    text: str
    scope: str
    repo: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: Source = Source.MANUAL
    confidence: Confidence = Confidence.HIGH
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PreferenceCreate(BaseModel):
    text: str
    scope: str
    repo: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: Source = Source.MANUAL


class PreferenceUpdate(BaseModel):
    text: str | None = None
    scope: str | None = None
    repo: str | None = None
    tags: list[str] | None = None


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"


class EmbedderConfig(BaseModel):
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"


class StorageConfig(BaseModel):
    path: str = "~/.engram/data"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 3000


class LoggingConfig(BaseModel):
    level: str = "INFO"


class EngramConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
```

- [ ] **Step 6: Create src/engram/config.py**

Loads config from `~/.engram/config.yaml`, falls back to repo default, resolves env vars.

```python
"""Configuration loader for engram."""

import logging
import os
import shutil
from pathlib import Path

import yaml

from engram.models import EngramConfig

logger = logging.getLogger(__name__)

ENGRAM_HOME = Path.home() / ".engram"
USER_CONFIG_PATH = ENGRAM_HOME / "config.yaml"
REPO_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def ensure_engram_home() -> None:
    """Create ~/.engram/ and subdirectories if they don't exist."""
    ENGRAM_HOME.mkdir(exist_ok=True)
    (ENGRAM_HOME / "data").mkdir(exist_ok=True)
    (ENGRAM_HOME / "logs").mkdir(exist_ok=True)


def ensure_user_config() -> None:
    """Copy default config to ~/.engram/config.yaml if it doesn't exist."""
    if not USER_CONFIG_PATH.exists() and REPO_CONFIG_PATH.exists():
        shutil.copy(REPO_CONFIG_PATH, USER_CONFIG_PATH)
        logger.info("Copied default config to %s", USER_CONFIG_PATH)


def load_config() -> EngramConfig:
    """Load configuration from ~/.engram/config.yaml, falling back to repo default."""
    ensure_engram_home()
    ensure_user_config()

    config_path = USER_CONFIG_PATH if USER_CONFIG_PATH.exists() else REPO_CONFIG_PATH

    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", config_path)
        return EngramConfig(**raw)

    logger.warning("No config file found, using defaults")
    return EngramConfig()


def save_config(config: EngramConfig) -> None:
    """Save configuration to ~/.engram/config.yaml."""
    ensure_engram_home()
    data = config.model_dump()
    with open(USER_CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    logger.info("Saved config to %s", USER_CONFIG_PATH)


def resolve_api_key(api_key_env: str) -> str | None:
    """Resolve API key from environment, then ~/.engram/.env file."""
    # Check environment first
    key = os.environ.get(api_key_env)
    if key:
        return key

    # Check ~/.engram/.env
    env_file = ENGRAM_HOME / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, _, value = line.partition("=")
                if name.strip() == api_key_env:
                    return value.strip()

    return None
```

- [ ] **Step 7: Create src/engram/logging.py**

```python
"""Structured logging setup for engram."""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure logging with console and optional file output."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

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
    )
```

Note: add `import logging.handlers` at the top of logging.py since `RotatingFileHandler` is in that submodule.

- [ ] **Step 8: Create justfile**

```just
# Engram — coding preference memory

set dotenv-load

# Development
dev:
    uv run uvicorn engram.server:app --reload --host 0.0.0.0 --port 3000

# Service management
start:
    launchctl load ~/Library/LaunchAgents/com.engram.service.plist

stop:
    launchctl unload ~/Library/LaunchAgents/com.engram.service.plist

restart: stop start

status:
    @launchctl list | grep engram || echo "engram is not running"

logs:
    tail -f ~/.engram/logs/engram.log

# Installation
install: install-service install-hook

uninstall: uninstall-hook uninstall-service

install-service:
    #!/usr/bin/env bash
    set -euo pipefail
    REPO_DIR="$(pwd)"
    UV_PATH="$(which uv)"
    cat > ~/Library/LaunchAgents/com.engram.service.plist << PLIST
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.engram.service</string>
        <key>ProgramArguments</key>
        <array>
            <string>${UV_PATH}</string>
            <string>run</string>
            <string>python</string>
            <string>-m</string>
            <string>engram.server</string>
        </array>
        <key>WorkingDirectory</key>
        <string>${REPO_DIR}</string>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>$HOME/.engram/logs/engram.log</string>
        <key>StandardErrorPath</key>
        <string>$HOME/.engram/logs/engram.log</string>
        <key>EnvironmentVariables</key>
        <dict>
            <key>PATH</key>
            <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        </dict>
    </dict>
    </plist>
    PLIST
    echo "Installed launchd plist"
    launchctl load ~/Library/LaunchAgents/com.engram.service.plist
    echo "Service started"

uninstall-service:
    -launchctl unload ~/Library/LaunchAgents/com.engram.service.plist
    rm -f ~/Library/LaunchAgents/com.engram.service.plist
    @echo "Removed launchd plist"

install-hook:
    #!/usr/bin/env bash
    set -euo pipefail
    SETTINGS_DIR="$HOME/.claude"
    mkdir -p "$SETTINGS_DIR"
    HOOK_SCRIPT="$SETTINGS_DIR/engram-hook.sh"
    cat > "$HOOK_SCRIPT" << 'HOOK'
    #!/usr/bin/env bash
    # Engram session injection hook
    # Detects project languages and repo, fetches preferences, writes to CLAUDE.md
    ENGRAM_URL="http://localhost:3000"
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"

    # Check if engram is running
    if ! curl -sf "$ENGRAM_URL/api/health" > /dev/null 2>&1; then
        exit 0
    fi

    # Detect repo name from git remote
    REPO=""
    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        REMOTE_URL=$(git config --get remote.origin.url 2>/dev/null || true)
        if [[ "$REMOTE_URL" =~ github[^:/]*[:/](.+)/([^/]+)$ ]]; then
            REPO="${BASH_REMATCH[2]%.git}"
        fi
    fi

    # Detect languages from file extensions
    SCOPES="global"
    if ls *.py **/*.py > /dev/null 2>&1; then SCOPES="$SCOPES,python"; fi
    if ls *.ts **/*.ts *.tsx **/*.tsx > /dev/null 2>&1; then SCOPES="$SCOPES,typescript"; fi
    if ls *.js **/*.js *.jsx **/*.jsx > /dev/null 2>&1; then SCOPES="$SCOPES,javascript"; fi
    if ls *.go **/*.go > /dev/null 2>&1; then SCOPES="$SCOPES,go"; fi
    if ls *.rs **/*.rs > /dev/null 2>&1; then SCOPES="$SCOPES,rust"; fi
    if ls *test* **/*test* > /dev/null 2>&1; then SCOPES="$SCOPES,testing"; fi

    # Fetch preferences
    QUERY="scopes=$SCOPES"
    if [[ -n "$REPO" ]]; then QUERY="$QUERY&repo=$REPO"; fi
    PREFS=$(curl -sf "$ENGRAM_URL/api/inject?$QUERY" 2>/dev/null || true)

    if [[ -z "$PREFS" ]]; then
        exit 0
    fi

    # Write managed block to CLAUDE.md
    touch "$CLAUDE_MD"
    # Remove existing engram block
    sed -i '' '/<!-- engram:start -->/,/<!-- engram:end -->/d' "$CLAUDE_MD"
    # Append new block
    printf '\n%s\n' "$PREFS" >> "$CLAUDE_MD"
    HOOK
    chmod +x "$HOOK_SCRIPT"
    echo "Installed hook script at $HOOK_SCRIPT"
    echo "Add this to your Claude Code settings.json hooks:"
    echo '  "hooks": { "SessionStart": [{ "command": "bash ~/.claude/engram-hook.sh" }] }'

uninstall-hook:
    rm -f ~/.claude/engram-hook.sh
    @echo "Removed engram hook script"
    @echo "Remember to remove the hook entry from Claude Code settings.json"

# Code quality
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

format:
    uv run ruff format src/ tests/

typecheck:
    uv run pyright

test *args:
    uv run pytest {{args}}

check: lint typecheck test

# Setup
setup:
    uv sync --all-extras
    @echo "Setup complete. Run 'just dev' to start the development server."

# Git operations (DannyMor account via ~/mydev/tools/github)
push:
    git push origin "$(git rev-parse --abbrev-ref HEAD)"

pr title body="":
    source ~/mydev/tools/github/gh_env.zsh && gpr "{{title}}" "{{body}}"

quick title body="":
    source ~/mydev/tools/github/gh_env.zsh && gquick "{{title}}" "{{body}}"
```

- [ ] **Step 9: Create tests/__init__.py and tests/conftest.py**

`tests/__init__.py` — empty file.

`tests/conftest.py`:

```python
"""Shared test fixtures for engram."""

import tempfile
from pathlib import Path

import pytest

from engram.config import EngramConfig, StorageConfig, LLMConfig, EmbedderConfig


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Provide a temporary directory for Qdrant storage."""
    storage_dir = tmp_path / "data"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def test_config(tmp_storage: Path) -> EngramConfig:
    """Provide a test configuration with temporary storage."""
    return EngramConfig(
        storage=StorageConfig(path=str(tmp_storage)),
        llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
    )
```

- [ ] **Step 10: Install dependencies and verify tooling**

Run: `cd /Users/dannymor/mydev/engram && uv sync --all-extras`
Expected: All dependencies installed successfully.

Run: `uv run ruff check src/ tests/`
Expected: No lint errors (or only minor fixable ones).

Run: `uv run pyright`
Expected: No type errors.

Run: `uv run pytest`
Expected: 0 tests collected, no errors.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml config.yaml .env.example justfile src/ tests/
git commit -m "feat: project scaffolding with uv, ruff, pyright, pytest, just"
```

---

### Task 2: Memory Layer

**Files:**
- Create: `src/engram/memory.py`
- Create: `tests/test_memory.py`

This task requires a running LLM (Anthropic API key) for Mem0's dedup features. Tests that exercise dedup will be marked to skip if no API key is available.

- [ ] **Step 1: Write failing tests for memory operations**

`tests/test_memory.py`:

```python
"""Tests for the memory layer."""

import os

import pytest

from engram.memory import MemoryStore
from engram.models import EngramConfig, PreferenceCreate, Source, StorageConfig, EmbedderConfig, LLMConfig


needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def memory_store(tmp_path):
    """Create a MemoryStore with temporary storage."""
    config = EngramConfig(
        storage=StorageConfig(path=str(tmp_path / "data")),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
        llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
    )
    return MemoryStore(config)


@needs_api_key
def test_add_preference(memory_store):
    pref = PreferenceCreate(
        text="Use pytest fixtures over setup/teardown methods",
        scope="python",
        tags=["testing", "pytest"],
        source=Source.MANUAL,
    )
    result = memory_store.add(pref)
    assert result.id is not None
    assert result.text == pref.text
    assert result.scope == "python"
    assert result.tags == ["testing", "pytest"]


@needs_api_key
def test_add_preference_with_repo(memory_store):
    pref = PreferenceCreate(
        text="Skip type annotations in this legacy codebase",
        scope="python",
        repo="legacy-app",
        tags=["typing"],
        source=Source.CODING_SESSION,
    )
    result = memory_store.add(pref)
    assert result.repo == "legacy-app"


@needs_api_key
def test_get_all_preferences(memory_store):
    memory_store.add(PreferenceCreate(text="Use dataclasses", scope="python"))
    memory_store.add(PreferenceCreate(text="Prefer const", scope="typescript"))

    all_prefs = memory_store.get_all()
    assert len(all_prefs) == 2

    python_prefs = memory_store.get_all(scope="python")
    assert len(python_prefs) == 1
    assert python_prefs[0].scope == "python"


@needs_api_key
def test_get_all_with_repo_filter(memory_store):
    memory_store.add(PreferenceCreate(text="Use strict types", scope="python", repo="engram"))
    memory_store.add(PreferenceCreate(text="Skip types", scope="python", repo="legacy"))
    memory_store.add(PreferenceCreate(text="Always lint", scope="python"))

    engram_prefs = memory_store.get_all(scope="python", repo="engram")
    # Should return repo-specific + universal (repo=None)
    assert len(engram_prefs) == 2
    texts = {p.text for p in engram_prefs}
    assert "Use strict types" in texts
    assert "Always lint" in texts
    assert "Skip types" not in texts


@needs_api_key
def test_search_preferences(memory_store):
    memory_store.add(PreferenceCreate(text="Use pytest fixtures for test setup", scope="python"))
    memory_store.add(PreferenceCreate(text="Prefer functional components in React", scope="react"))

    results = memory_store.search("testing setup", scope="python")
    assert len(results) >= 1
    assert any("pytest" in r.text.lower() or "test" in r.text.lower() for r in results)


@needs_api_key
def test_delete_preference(memory_store):
    pref = memory_store.add(PreferenceCreate(text="Temporary pref", scope="global"))
    memory_store.delete(pref.id)

    all_prefs = memory_store.get_all()
    assert not any(p.id == pref.id for p in all_prefs)


@needs_api_key
def test_update_preference(memory_store):
    pref = memory_store.add(PreferenceCreate(text="Use dicts", scope="python"))
    updated = memory_store.update(pref.id, text="Use dataclasses instead of dicts")
    assert updated.text == "Use dataclasses instead of dicts"
    assert updated.id == pref.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_memory.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'engram.memory'`

- [ ] **Step 3: Implement memory.py**

`src/engram/memory.py`:

```python
"""Memory layer — Mem0 wrapper with preference schema and scoping."""

import logging
from pathlib import Path

from mem0 import Memory

from engram.models import (
    Confidence,
    EngramConfig,
    Preference,
    PreferenceCreate,
    PreferenceUpdate,
)

logger = logging.getLogger(__name__)


class MemoryStore:
    """Wraps Mem0 to provide preference-specific storage with scoping."""

    USER_ID = "engram_user"

    def __init__(self, config: EngramConfig) -> None:
        storage_path = Path(config.storage.path).expanduser()
        storage_path.mkdir(parents=True, exist_ok=True)

        mem0_config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "engram_preferences",
                    "path": str(storage_path),
                },
            },
            "embedder": {
                "provider": config.embedder.provider,
                "config": {
                    "model": config.embedder.model,
                },
            },
            "llm": {
                "provider": config.llm.provider,
                "config": {
                    "model": config.llm.model,
                },
            },
        }

        self._mem0 = Memory.from_config(mem0_config)
        self._has_llm = True
        logger.info("MemoryStore initialized with storage at %s", storage_path)

    def add(self, pref: PreferenceCreate) -> Preference:
        """Add a preference. Mem0 handles dedup via LLM."""
        metadata = {
            "scope": pref.scope,
            "repo": pref.repo,
            "tags": pref.tags,
            "source": pref.source.value,
            "confidence": Confidence.HIGH.value,
        }

        kwargs: dict = {
            "user_id": self.USER_ID,
            "metadata": metadata,
        }

        if not self._has_llm:
            kwargs["infer"] = False

        result = self._mem0.add(pref.text, **kwargs)
        logger.info(
            "Added preference (scope=%s, repo=%s): %s",
            pref.scope,
            pref.repo,
            pref.text[:80],
        )

        # Extract the created/updated memory from result
        memory_id = self._extract_id(result)
        return self._get_by_id(memory_id, pref)

    def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Preference]:
        """Semantic search for preferences."""
        filters = self._build_filters(scope=scope, repo=repo)
        kwargs: dict = {"user_id": self.USER_ID}
        if filters:
            kwargs["filters"] = filters

        results = self._mem0.search(query, **kwargs)
        prefs = [self._to_preference(m) for m in results.get("results", results)]
        logger.info("Search query=%s scope=%s repo=%s returned %d results", query, scope, repo, len(prefs))
        return prefs

    def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Preference]:
        """List all preferences, optionally filtered."""
        all_memories = self._mem0.get_all(user_id=self.USER_ID)
        memories = all_memories.get("results", all_memories)

        prefs = [self._to_preference(m) for m in memories]

        # Apply filters in Python since Mem0 get_all filtering is limited
        if scope:
            prefs = [p for p in prefs if p.scope == scope]
        if repo is not None:
            # Include repo-specific + universal (repo=None)
            prefs = [p for p in prefs if p.repo == repo or p.repo is None]
        if tags:
            prefs = [p for p in prefs if any(t in p.tags for t in tags)]

        return prefs

    def delete(self, preference_id: str) -> None:
        """Hard delete a preference."""
        self._mem0.delete(preference_id)
        logger.info("Deleted preference %s", preference_id)

    def update(
        self,
        preference_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Preference:
        """Update an existing preference."""
        existing = self._mem0.get(preference_id)

        if text:
            self._mem0.update(preference_id, data=text)

        # Update metadata if any metadata fields changed
        current_metadata = existing.get("metadata", {})
        if scope is not None:
            current_metadata["scope"] = scope
        if repo is not None:
            current_metadata["repo"] = repo
        if tags is not None:
            current_metadata["tags"] = tags

        # Re-fetch to return current state
        updated = self._mem0.get(preference_id)
        logger.info("Updated preference %s", preference_id)
        return self._to_preference(updated)

    def get_scopes(self) -> list[str]:
        """Return all distinct scopes in use."""
        all_prefs = self.get_all()
        return sorted({p.scope for p in all_prefs})

    def get_tags(self) -> list[str]:
        """Return all distinct tags in use."""
        all_prefs = self.get_all()
        tags: set[str] = set()
        for p in all_prefs:
            tags.update(p.tags)
        return sorted(tags)

    def _extract_id(self, result: dict | list) -> str:
        """Extract memory ID from Mem0 add() result."""
        if isinstance(result, dict):
            results = result.get("results", [])
            if results:
                return results[0].get("id", results[0].get("memory_id", ""))
        if isinstance(result, list) and result:
            return result[0].get("id", result[0].get("memory_id", ""))
        return ""

    def _get_by_id(self, memory_id: str, fallback: PreferenceCreate) -> Preference:
        """Fetch a memory by ID and convert to Preference."""
        if memory_id:
            try:
                mem = self._mem0.get(memory_id)
                return self._to_preference(mem)
            except Exception:
                logger.warning("Could not fetch memory %s, using fallback", memory_id)

        return Preference(
            id=memory_id or "unknown",
            text=fallback.text,
            scope=fallback.scope,
            repo=fallback.repo,
            tags=fallback.tags,
            source=fallback.source,
        )

    def _to_preference(self, memory: dict) -> Preference:
        """Convert a Mem0 memory dict to a Preference model."""
        metadata = memory.get("metadata", {})
        return Preference(
            id=memory.get("id", memory.get("memory_id", "")),
            text=memory.get("memory", ""),
            scope=metadata.get("scope", "global"),
            repo=metadata.get("repo"),
            tags=metadata.get("tags", []),
            source=metadata.get("source", "manual"),
            confidence=metadata.get("confidence", "high"),
            created_at=memory.get("created_at"),
            updated_at=memory.get("updated_at"),
        )

    def _build_filters(
        self, scope: str | None = None, repo: str | None = None
    ) -> dict | None:
        """Build Mem0-compatible filter dict."""
        conditions = []
        if scope:
            conditions.append({"scope": scope})
        if repo is not None:
            conditions.append({"OR": [{"repo": repo}, {"repo": None}]})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"AND": conditions}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_memory.py -v`
Expected: All tests with `@needs_api_key` pass if ANTHROPIC_API_KEY is set, otherwise skipped.

- [ ] **Step 5: Run linting and type checking**

Run: `uv run ruff check src/engram/memory.py && uv run pyright src/engram/memory.py`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/engram/memory.py tests/test_memory.py
git commit -m "feat: memory layer with Mem0 wrapper, scoping, and repo filtering"
```

---

### Task 3: Server — REST API

**Files:**
- Create: `src/engram/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for REST API endpoints**

`tests/test_server.py`:

```python
"""Tests for the REST API server."""

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from engram.models import Preference, Source, Confidence


needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def mock_memory():
    """Create a mock MemoryStore."""
    store = MagicMock()
    store.get_all.return_value = [
        Preference(
            id="test-1",
            text="Use pytest fixtures",
            scope="python",
            tags=["testing"],
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        )
    ]
    store.search.return_value = [
        Preference(
            id="test-1",
            text="Use pytest fixtures",
            scope="python",
            tags=["testing"],
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        )
    ]
    store.get_scopes.return_value = ["python", "global"]
    store.get_tags.return_value = ["testing", "pytest"]
    return store


@pytest.fixture
def app(mock_memory):
    """Create test app with mocked memory store."""
    from engram.server import create_app
    return create_app(memory_store=mock_memory)


@pytest.fixture
async def client(app):
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_list_preferences(client, mock_memory):
    response = await client.get("/api/preferences")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "Use pytest fixtures"
    mock_memory.get_all.assert_called_once()


async def test_list_preferences_with_scope_filter(client, mock_memory):
    response = await client.get("/api/preferences?scope=python")
    assert response.status_code == 200
    mock_memory.get_all.assert_called_once_with(scope="python", repo=None, tags=None)


async def test_search_preferences(client, mock_memory):
    response = await client.get("/api/preferences?q=testing")
    assert response.status_code == 200
    mock_memory.search.assert_called_once_with("testing", scope=None, repo=None)


async def test_add_preference(client, mock_memory):
    mock_memory.add.return_value = Preference(
        id="new-1",
        text="Use dataclasses",
        scope="python",
        tags=[],
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )
    response = await client.post(
        "/api/preferences",
        json={"text": "Use dataclasses", "scope": "python"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Use dataclasses"


async def test_delete_preference(client, mock_memory):
    response = await client.delete("/api/preferences/test-1")
    assert response.status_code == 204
    mock_memory.delete.assert_called_once_with("test-1")


async def test_update_preference(client, mock_memory):
    mock_memory.update.return_value = Preference(
        id="test-1",
        text="Updated text",
        scope="python",
        tags=["testing"],
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )
    response = await client.put(
        "/api/preferences/test-1",
        json={"text": "Updated text"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Updated text"


async def test_get_scopes(client, mock_memory):
    response = await client.get("/api/scopes")
    assert response.status_code == 200
    assert response.json() == ["python", "global"]


async def test_get_tags(client, mock_memory):
    response = await client.get("/api/tags")
    assert response.status_code == 200
    assert response.json() == ["testing", "pytest"]


async def test_inject_preferences(client, mock_memory):
    response = await client.get("/api/inject?scopes=python,global")
    assert response.status_code == 200
    text = response.text
    assert "<!-- engram:start -->" in text
    assert "<!-- engram:end -->" in text
    assert "Use pytest fixtures" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engram.server'`

- [ ] **Step 3: Implement server.py**

`src/engram/server.py`:

```python
"""FastAPI server — REST API, MCP endpoint, and static UI."""

import logging
from pathlib import Path

from fastapi import FastAPI, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from engram.config import load_config, save_config, resolve_api_key, ENGRAM_HOME
from engram.logging import setup_logging
from engram.memory import MemoryStore
from engram.models import (
    EngramConfig,
    Preference,
    PreferenceCreate,
    PreferenceUpdate,
)

logger = logging.getLogger(__name__)

UI_DIR = Path(__file__).parent.parent.parent / "ui"


def create_app(
    config: EngramConfig | None = None,
    memory_store: MemoryStore | None = None,
) -> FastAPI:
    """Create the FastAPI application."""
    if config is None:
        config = load_config()

    setup_logging(
        level=config.logging.level,
        log_dir=ENGRAM_HOME / "logs",
    )

    app = FastAPI(title="Engram", version="0.1.0")

    if memory_store is None:
        memory_store = MemoryStore(config)

    # Store references on app state
    app.state.config = config
    app.state.memory = memory_store

    # --- Health ---

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    # --- Preferences CRUD ---

    @app.get("/api/preferences", response_model=list[Preference])
    async def list_preferences(
        q: str | None = Query(None, description="Semantic search query"),
        scope: str | None = Query(None),
        repo: str | None = Query(None),
        tags: str | None = Query(None, description="Comma-separated tags"),
    ):
        if q:
            return app.state.memory.search(q, scope=scope, repo=repo)
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        return app.state.memory.get_all(scope=scope, repo=repo, tags=tag_list)

    @app.post("/api/preferences", response_model=Preference, status_code=201)
    async def add_preference(pref: PreferenceCreate):
        return app.state.memory.add(pref)

    @app.get("/api/preferences/{preference_id}", response_model=Preference)
    async def get_preference(preference_id: str):
        # Mem0 get() returns a dict
        mem = app.state.memory._mem0.get(preference_id)
        return app.state.memory._to_preference(mem)

    @app.put("/api/preferences/{preference_id}", response_model=Preference)
    async def update_preference(preference_id: str, update: PreferenceUpdate):
        return app.state.memory.update(
            preference_id,
            text=update.text,
            scope=update.scope,
            repo=update.repo,
            tags=update.tags,
        )

    @app.delete("/api/preferences/{preference_id}", status_code=204)
    async def delete_preference(preference_id: str):
        app.state.memory.delete(preference_id)
        return Response(status_code=204)

    # --- Scopes & Tags ---

    @app.get("/api/scopes", response_model=list[str])
    async def list_scopes():
        return app.state.memory.get_scopes()

    @app.get("/api/tags", response_model=list[str])
    async def list_tags():
        return app.state.memory.get_tags()

    # --- Injection ---

    @app.get("/api/inject")
    async def inject_preferences(
        scopes: str = Query("global", description="Comma-separated scopes"),
        repo: str | None = Query(None),
    ):
        """Return formatted preference block for CLAUDE.md injection."""
        scope_list = [s.strip() for s in scopes.split(",")]
        all_prefs: list[Preference] = []
        seen_ids: set[str] = set()

        for scope in scope_list:
            prefs = app.state.memory.get_all(scope=scope, repo=repo)
            for p in prefs:
                if p.id not in seen_ids:
                    all_prefs.append(p)
                    seen_ids.add(p.id)

        if not all_prefs:
            return Response(content="", media_type="text/plain")

        lines = ["<!-- engram:start -->", "## Coding Preferences (managed by engram)"]
        for p in all_prefs:
            lines.append(f"- {p.text}")
        lines.append("<!-- engram:end -->")

        logger.info("Injection: scopes=%s repo=%s returned %d prefs", scopes, repo, len(all_prefs))
        return Response(content="\n".join(lines), media_type="text/plain")

    # --- Config ---

    @app.get("/api/config")
    async def get_config():
        cfg = app.state.config
        # Mask API key presence, don't return the actual key
        has_key = resolve_api_key(cfg.llm.api_key_env) is not None
        return {
            "llm": {"provider": cfg.llm.provider, "model": cfg.llm.model, "has_api_key": has_key},
            "embedder": {"provider": cfg.embedder.provider, "model": cfg.embedder.model},
            "storage": {"path": cfg.storage.path},
        }

    @app.put("/api/config")
    async def update_config(new_config: EngramConfig):
        app.state.config = new_config
        save_config(new_config)
        logger.info("Configuration updated")
        return {"status": "updated"}

    # --- Static UI ---

    @app.get("/", response_class=HTMLResponse)
    async def serve_ui():
        index_path = UI_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse("<h1>Engram</h1><p>UI not built yet.</p>")

    logger.info("Engram server created on port %d", config.server.port)
    return app


# Entry point for `python -m engram.server`
def main() -> None:
    import uvicorn

    config = load_config()
    setup_logging(level=config.logging.level, log_dir=ENGRAM_HOME / "logs")
    logger.info("Starting engram server on %s:%d", config.server.host, config.server.port)
    app = create_app(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
```

Also create `src/engram/__main__.py` so `python -m engram.server` works:

```python
"""Allow running engram as a module: python -m engram.server"""

from engram.server import main

main()
```

Wait — that would make `python -m engram` run the server. The plist runs `python -m engram.server`, so we need `src/engram/server/__main__.py`... Actually, simpler: just add a `__main__.py` at the package level that calls server main:

`src/engram/__main__.py`:

```python
"""Entry point for python -m engram."""

from engram.server import main

main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`
Expected: All tests pass (these use mocked memory, no API key needed).

- [ ] **Step 5: Run linting and type checking**

Run: `uv run ruff check src/engram/server.py && uv run pyright src/engram/server.py`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/engram/server.py src/engram/__main__.py tests/test_server.py
git commit -m "feat: REST API server with preferences CRUD, injection, and config endpoints"
```

---

### Task 4: MCP Server Integration

**Files:**
- Create: `src/engram/mcp.py`
- Modify: `src/engram/server.py` — mount MCP app

- [ ] **Step 1: Create src/engram/mcp.py**

The MCP server defines tools that map to memory operations. FastMCP provides the MCP protocol handling.

```python
"""MCP server — exposes preference tools for Claude Code."""

import logging

from fastmcp import FastMCP

from engram.memory import MemoryStore
from engram.models import PreferenceCreate, Source

logger = logging.getLogger(__name__)

DESCRIPTION = """Engram is the user's coding preference memory. When the user gives feedback \
about how code should be written — coding style, patterns to use or avoid, testing approaches, \
naming conventions, architectural preferences — call add_preference() to store it. Examples: \
"don't mock the database in tests", "use frozen dataclasses", "prefer composition over \
inheritance". Do not store task-specific instructions or one-off corrections. At session start, \
preferences are already loaded into context via CLAUDE.md — do not call \
get_preferences_for_context() yourself."""


def create_mcp(memory_store: MemoryStore) -> FastMCP:
    """Create the MCP server with preference tools."""
    mcp = FastMCP("engram", description=DESCRIPTION)

    @mcp.tool()
    def add_preference(
        text: str,
        scope: str,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Store a coding preference. Called when the user gives feedback about coding style."""
        pref = PreferenceCreate(
            text=text,
            scope=scope,
            repo=repo,
            tags=tags or [],
            source=Source.CODING_SESSION,
        )
        result = memory_store.add(pref)
        logger.info("MCP add_preference: scope=%s repo=%s text=%s", scope, repo, text[:80])
        return result.model_dump(mode="json")

    @mcp.tool()
    def get_preferences_for_context(
        languages: list[str] | None = None,
        repo: str | None = None,
    ) -> list[dict]:
        """Get relevant preferences for the current session context."""
        scopes = ["global"] + (languages or [])
        all_prefs = []
        seen_ids: set[str] = set()

        for scope in scopes:
            for p in memory_store.get_all(scope=scope, repo=repo):
                if p.id not in seen_ids:
                    all_prefs.append(p.model_dump(mode="json"))
                    seen_ids.add(p.id)

        logger.info("MCP get_preferences_for_context: scopes=%s repo=%s returned %d", scopes, repo, len(all_prefs))
        return all_prefs

    @mcp.tool()
    def search_preferences(
        query: str,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Semantic search across all stored preferences."""
        results = memory_store.search(query, scope=scope, repo=repo)
        logger.info("MCP search_preferences: query=%s returned %d", query[:50], len(results))
        return [r.model_dump(mode="json") for r in results]

    @mcp.tool()
    def list_preferences(
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """List all stored preferences, optionally filtered."""
        results = memory_store.get_all(scope=scope, repo=repo, tags=tags)
        return [r.model_dump(mode="json") for r in results]

    @mcp.tool()
    def delete_preference(id: str) -> dict:
        """Permanently delete a preference by ID."""
        memory_store.delete(id)
        logger.info("MCP delete_preference: id=%s", id)
        return {"deleted": id}

    @mcp.tool()
    def update_preference(
        id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Update an existing preference."""
        result = memory_store.update(id, text=text, scope=scope, repo=repo, tags=tags)
        logger.info("MCP update_preference: id=%s", id)
        return result.model_dump(mode="json")

    return mcp
```

- [ ] **Step 2: Mount MCP on the FastAPI server**

Add to `src/engram/server.py`, inside `create_app()`, after the memory store is created:

```python
    # --- MCP ---
    from engram.mcp import create_mcp
    mcp = create_mcp(memory_store)
    mcp_app = mcp.streamable_http_app()
    app.mount("/mcp", mcp_app)
    logger.info("MCP server mounted at /mcp")
```

Add this block after `app.state.memory = memory_store` and before the health endpoint.

- [ ] **Step 3: Verify the server starts with MCP**

Run: `uv run python -c "from engram.server import create_app; app = create_app(); print('OK')"`
Expected: Prints "OK" without errors (will create a MemoryStore, needs API key or will warn).

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: All existing tests still pass. Server tests work because they mock memory_store and don't go through MCP mount.

- [ ] **Step 5: Commit**

```bash
git add src/engram/mcp.py src/engram/server.py
git commit -m "feat: MCP server with preference tools mounted at /mcp"
```

---

### Task 5: Session Injector

**Files:**
- Create: `src/engram/injector.py`
- Create: `tests/test_injector.py`

The injector module generates the CLAUDE.md preference block. The actual hook script is in the justfile (already created in Task 1). This module provides the formatting logic used by the `/api/inject` endpoint.

- [ ] **Step 1: Write failing tests for injector**

`tests/test_injector.py`:

```python
"""Tests for the session injector."""

from engram.injector import format_injection_block, detect_scopes_from_extensions
from engram.models import Preference, Source, Confidence


def test_format_injection_block_with_prefs():
    prefs = [
        Preference(id="1", text="Use pytest fixtures", scope="python", source=Source.MANUAL, confidence=Confidence.HIGH),
        Preference(id="2", text="Prefer frozen dataclasses", scope="python", source=Source.MANUAL, confidence=Confidence.HIGH),
    ]
    block = format_injection_block(prefs)
    assert "<!-- engram:start -->" in block
    assert "<!-- engram:end -->" in block
    assert "- Use pytest fixtures" in block
    assert "- Prefer frozen dataclasses" in block


def test_format_injection_block_empty():
    block = format_injection_block([])
    assert block == ""


def test_detect_scopes_from_extensions():
    extensions = {".py", ".pyx"}
    scopes = detect_scopes_from_extensions(extensions)
    assert "python" in scopes
    assert "global" in scopes


def test_detect_scopes_multiple_languages():
    extensions = {".py", ".ts", ".tsx"}
    scopes = detect_scopes_from_extensions(extensions)
    assert "python" in scopes
    assert "typescript" in scopes
    assert "global" in scopes


def test_detect_scopes_with_test_files():
    extensions = {".py"}
    scopes = detect_scopes_from_extensions(extensions, has_test_files=True)
    assert "testing" in scopes


def test_detect_scopes_unknown_extension():
    extensions = {".xyz"}
    scopes = detect_scopes_from_extensions(extensions)
    assert scopes == ["global"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_injector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engram.injector'`

- [ ] **Step 3: Implement injector.py**

`src/engram/injector.py`:

```python
"""Session injector — generates CLAUDE.md preference blocks."""

import logging

from engram.models import Preference

logger = logging.getLogger(__name__)

EXTENSION_TO_SCOPE: dict[str, str] = {
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "cpp",
    ".h": "cpp",
}


def detect_scopes_from_extensions(
    extensions: set[str], has_test_files: bool = False
) -> list[str]:
    """Map file extensions to preference scopes."""
    scopes = {"global"}
    for ext in extensions:
        scope = EXTENSION_TO_SCOPE.get(ext)
        if scope:
            scopes.add(scope)
    if has_test_files:
        scopes.add("testing")
    return sorted(scopes)


def format_injection_block(prefs: list[Preference]) -> str:
    """Format preferences as a CLAUDE.md managed block."""
    if not prefs:
        return ""

    lines = [
        "<!-- engram:start -->",
        "## Coding Preferences (managed by engram)",
        "",
    ]
    for p in prefs:
        lines.append(f"- {p.text}")
    lines.append("<!-- engram:end -->")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_injector.py -v`
Expected: All 6 tests pass.

- [ ] **Step 5: Update /api/inject endpoint to use injector module**

In `src/engram/server.py`, update the inject endpoint to use the injector module:

Replace the inject endpoint body with:

```python
    @app.get("/api/inject")
    async def inject_preferences(
        scopes: str = Query("global", description="Comma-separated scopes"),
        repo: str | None = Query(None),
    ):
        """Return formatted preference block for CLAUDE.md injection."""
        from engram.injector import format_injection_block

        scope_list = [s.strip() for s in scopes.split(",")]
        all_prefs: list[Preference] = []
        seen_ids: set[str] = set()

        for scope in scope_list:
            prefs = app.state.memory.get_all(scope=scope, repo=repo)
            for p in prefs:
                if p.id not in seen_ids:
                    all_prefs.append(p)
                    seen_ids.add(p.id)

        block = format_injection_block(all_prefs)
        logger.info("Injection: scopes=%s repo=%s returned %d prefs", scopes, repo, len(all_prefs))
        return Response(content=block, media_type="text/plain")
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/engram/injector.py tests/test_injector.py src/engram/server.py
git commit -m "feat: session injector with scope detection and CLAUDE.md block formatting"
```

---

### Task 6: Curation Agent

**Files:**
- Create: `src/engram/curator.py`
- Create: `tests/test_curator.py`
- Modify: `src/engram/server.py` — add `/api/chat` endpoint

- [ ] **Step 1: Write failing tests for curation agent**

`tests/test_curator.py`:

```python
"""Tests for the curation agent."""

import os

import pytest

from engram.curator import CurationAgent, build_system_prompt
from engram.models import Preference, Source, Confidence


def test_build_system_prompt_with_prefs():
    prefs = [
        Preference(id="1", text="Use pytest fixtures", scope="python", tags=["testing"], source=Source.MANUAL, confidence=Confidence.HIGH),
        Preference(id="2", text="Prefer composition", scope="global", tags=[], source=Source.MANUAL, confidence=Confidence.HIGH),
    ]
    prompt = build_system_prompt(prefs)
    assert "Use pytest fixtures" in prompt
    assert "Prefer composition" in prompt
    assert "python" in prompt
    assert "preference" in prompt.lower()


def test_build_system_prompt_empty():
    prompt = build_system_prompt([])
    assert "no preferences" in prompt.lower() or "empty" in prompt.lower() or "none" in prompt.lower()


def test_build_tool_definitions():
    from engram.curator import build_tool_definitions
    tools = build_tool_definitions()
    tool_names = [t["name"] for t in tools]
    assert "add_preference" in tool_names
    assert "search_preferences" in tool_names
    assert "delete_preference" in tool_names
    assert "update_preference" in tool_names
    assert "list_preferences" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_curator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engram.curator'`

- [ ] **Step 3: Implement curator.py**

`src/engram/curator.py`:

```python
"""Curation agent — preference management via Anthropic API with tool use."""

import json
import logging
from collections.abc import AsyncGenerator

import anthropic

from engram.config import resolve_api_key
from engram.memory import MemoryStore
from engram.models import (
    ChatMessage,
    EngramConfig,
    Preference,
    PreferenceCreate,
    Source,
)

logger = logging.getLogger(__name__)


def build_system_prompt(prefs: list[Preference]) -> str:
    """Build the curation agent system prompt with current preferences."""
    if not prefs:
        pref_section = "There are currently no stored preferences."
    else:
        lines = []
        for p in prefs:
            tags_str = f" [{', '.join(p.tags)}]" if p.tags else ""
            repo_str = f" (repo: {p.repo})" if p.repo else ""
            lines.append(f"- [{p.scope}]{repo_str}{tags_str} {p.text} (id: {p.id})")
        pref_section = "\n".join(lines)

    return f"""You are Engram's curation agent — a preference management assistant.

Your job is to help the user manage their coding preferences. You can:
- Add new preferences
- Search for existing preferences
- Update preferences (text, scope, tags, repo)
- Delete preferences
- Analyze preferences for conflicts or gaps
- Suggest preferences for new projects or languages

Current stored preferences:
{pref_section}

When the user asks you to modify preferences, use the provided tools.
When analyzing or summarizing, work from the preference list above.
Be concise and direct. Reference preference IDs when discussing specific items."""


def build_tool_definitions() -> list[dict]:
    """Build Anthropic-compatible tool definitions for the curation agent."""
    return [
        {
            "name": "add_preference",
            "description": "Add a new coding preference",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The preference text"},
                    "scope": {"type": "string", "description": "Scope: global, python, typescript, etc."},
                    "repo": {"type": ["string", "null"], "description": "Optional repo name, null for universal"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                },
                "required": ["text", "scope"],
            },
        },
        {
            "name": "search_preferences",
            "description": "Semantic search across stored preferences",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "scope": {"type": ["string", "null"], "description": "Optional scope filter"},
                    "repo": {"type": ["string", "null"], "description": "Optional repo filter"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_preferences",
            "description": "List all preferences, optionally filtered",
            "input_schema": {
                "type": "object",
                "properties": {
                    "scope": {"type": ["string", "null"], "description": "Optional scope filter"},
                    "repo": {"type": ["string", "null"], "description": "Optional repo filter"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tag filter"},
                },
            },
        },
        {
            "name": "delete_preference",
            "description": "Delete a preference by ID",
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Preference ID to delete"},
                },
                "required": ["id"],
            },
        },
        {
            "name": "update_preference",
            "description": "Update an existing preference",
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Preference ID to update"},
                    "text": {"type": ["string", "null"], "description": "New text"},
                    "scope": {"type": ["string", "null"], "description": "New scope"},
                    "repo": {"type": ["string", "null"], "description": "New repo"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "New tags"},
                },
                "required": ["id"],
            },
        },
    ]


class CurationAgent:
    """Manages conversations with the curation agent."""

    def __init__(self, config: EngramConfig, memory_store: MemoryStore) -> None:
        api_key = resolve_api_key(config.llm.api_key_env)
        if not api_key:
            raise ValueError(f"API key not found for {config.llm.api_key_env}")

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = config.llm.model
        self._memory = memory_store
        self._tools = build_tool_definitions()

    async def chat(
        self, message: str, history: list[ChatMessage]
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the curation agent, executing tool calls as needed."""
        all_prefs = self._memory.get_all()
        system_prompt = build_system_prompt(all_prefs)

        messages = [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": message})

        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=self._tools,
            )

            # Check if there are tool calls to execute
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            if not tool_calls:
                # No tool calls — yield the text response
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            # Execute tool calls and continue the conversation
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    yield block.text
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and add results
            tool_results = []
            for tc in tool_calls:
                result = self._execute_tool(tc.name, tc.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

    def _execute_tool(self, name: str, args: dict) -> dict | list | str:
        """Execute a tool call against the memory store."""
        logger.info("Curation agent tool call: %s(%s)", name, args)

        if name == "add_preference":
            pref = PreferenceCreate(
                text=args["text"],
                scope=args["scope"],
                repo=args.get("repo"),
                tags=args.get("tags", []),
                source=Source.CURATION_AGENT,
            )
            result = self._memory.add(pref)
            return result.model_dump(mode="json")

        elif name == "search_preferences":
            results = self._memory.search(
                args["query"],
                scope=args.get("scope"),
                repo=args.get("repo"),
            )
            return [r.model_dump(mode="json") for r in results]

        elif name == "list_preferences":
            results = self._memory.get_all(
                scope=args.get("scope"),
                repo=args.get("repo"),
                tags=args.get("tags"),
            )
            return [r.model_dump(mode="json") for r in results]

        elif name == "delete_preference":
            self._memory.delete(args["id"])
            return {"deleted": args["id"]}

        elif name == "update_preference":
            result = self._memory.update(
                args["id"],
                text=args.get("text"),
                scope=args.get("scope"),
                repo=args.get("repo"),
                tags=args.get("tags"),
            )
            return result.model_dump(mode="json")

        else:
            return {"error": f"Unknown tool: {name}"}
```

- [ ] **Step 4: Add /api/chat endpoint to server.py**

Add to `src/engram/server.py` inside `create_app()`, after the config endpoints:

```python
    # --- Chat (Curation Agent) ---

    from fastapi.responses import StreamingResponse
    from engram.curator import CurationAgent
    from engram.models import ChatRequest

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """Stream a curation agent response."""
        try:
            agent = CurationAgent(app.state.config, app.state.memory)
        except ValueError as e:
            return Response(content=str(e), status_code=503)

        async def stream():
            async for chunk in agent.chat(request.message, request.history):
                yield chunk

        return StreamingResponse(stream(), media_type="text/plain")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_curator.py -v`
Expected: All 3 tests pass (they test prompt building and tool definitions, no API calls).

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/engram/curator.py tests/test_curator.py src/engram/server.py
git commit -m "feat: curation agent with tool use and streaming chat endpoint"
```

---

### Task 7: Web UI

**Files:**
- Create: `ui/index.html`

This is a single HTML file with Alpine.js, Tailwind CSS, and Lucide Icons via CDN. Contains all three views: Preferences, Chat, and Settings.

- [ ] **Step 1: Create ui/index.html**

This is a large file. The key sections:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Engram — Coding Preferences</title>
    <script src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js" defer></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        engram: {
                            50: '#f0f4ff',
                            100: '#dbe4ff',
                            500: '#4c6ef5',
                            600: '#3b5bdb',
                            700: '#364fc7',
                            800: '#1e3a5f',
                            900: '#0f1f3d',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        [x-cloak] { display: none !important; }
    </style>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen" x-data="engram()" x-init="init()">

    <!-- Navigation -->
    <nav class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
            <i data-lucide="brain" class="w-6 h-6 text-engram-600"></i>
            <span class="font-semibold text-lg">Engram</span>
        </div>
        <div class="flex gap-1">
            <button @click="view = 'preferences'" :class="view === 'preferences' ? 'bg-engram-50 text-engram-700' : 'text-gray-500 hover:text-gray-700'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Preferences
            </button>
            <button @click="view = 'chat'" :class="view === 'chat' ? 'bg-engram-50 text-engram-700' : 'text-gray-500 hover:text-gray-700'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Chat
            </button>
            <button @click="view = 'settings'" :class="view === 'settings' ? 'bg-engram-50 text-engram-700' : 'text-gray-500 hover:text-gray-700'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Settings
            </button>
        </div>
    </nav>

    <!-- Preferences View -->
    <div x-show="view === 'preferences'" x-cloak class="max-w-6xl mx-auto p-6">
        <div class="flex gap-6">
            <!-- Sidebar: scopes and tags -->
            <div class="w-56 flex-shrink-0">
                <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Scopes</h3>
                <div class="space-y-1 mb-6">
                    <button @click="filterScope = null; loadPreferences()" :class="!filterScope ? 'bg-engram-50 text-engram-700 font-medium' : 'text-gray-600 hover:bg-gray-100'" class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors">All</button>
                    <template x-for="s in scopes" :key="s">
                        <button @click="filterScope = s; loadPreferences()" :class="filterScope === s ? 'bg-engram-50 text-engram-700 font-medium' : 'text-gray-600 hover:bg-gray-100'" class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors" x-text="s"></button>
                    </template>
                </div>
                <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Tags</h3>
                <div class="space-y-1">
                    <template x-for="t in tags" :key="t">
                        <button @click="toggleTag(t); loadPreferences()" :class="filterTags.includes(t) ? 'bg-engram-50 text-engram-700 font-medium' : 'text-gray-600 hover:bg-gray-100'" class="w-full text-left px-3 py-1.5 rounded text-sm transition-colors" x-text="t"></button>
                    </template>
                </div>
            </div>

            <!-- Main content -->
            <div class="flex-1">
                <!-- Search + Add -->
                <div class="flex gap-3 mb-6">
                    <div class="relative flex-1">
                        <i data-lucide="search" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"></i>
                        <input type="text" x-model="searchQuery" @input.debounce.300ms="loadPreferences()" placeholder="Search preferences..." class="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-engram-500 focus:border-transparent">
                    </div>
                    <button @click="showAddModal = true" class="bg-engram-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-engram-700 transition-colors flex items-center gap-2">
                        <i data-lucide="plus" class="w-4 h-4"></i> Add
                    </button>
                </div>

                <!-- Preference cards -->
                <div class="space-y-3">
                    <template x-for="pref in preferences" :key="pref.id">
                        <div class="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors">
                            <div class="flex items-start justify-between">
                                <div class="flex-1">
                                    <template x-if="editingId !== pref.id">
                                        <p class="text-sm text-gray-800" x-text="pref.text"></p>
                                    </template>
                                    <template x-if="editingId === pref.id">
                                        <input type="text" x-model="editText" @keydown.enter="saveEdit(pref.id)" @keydown.escape="editingId = null" class="w-full text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-engram-500">
                                    </template>
                                    <div class="flex items-center gap-2 mt-2">
                                        <span class="inline-block bg-engram-50 text-engram-700 text-xs px-2 py-0.5 rounded font-medium" x-text="pref.scope"></span>
                                        <span x-show="pref.repo" class="inline-block bg-orange-50 text-orange-700 text-xs px-2 py-0.5 rounded font-medium" x-text="pref.repo"></span>
                                        <template x-for="tag in pref.tags" :key="tag">
                                            <span class="inline-block bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded" x-text="tag"></span>
                                        </template>
                                        <span x-show="pref.confidence === 'low'" class="inline-block bg-yellow-50 text-yellow-700 text-xs px-2 py-0.5 rounded font-medium">needs review</span>
                                    </div>
                                </div>
                                <div class="flex items-center gap-1 ml-4">
                                    <button @click="startEdit(pref)" class="p-1.5 text-gray-400 hover:text-gray-600 rounded transition-colors">
                                        <i data-lucide="pencil" class="w-3.5 h-3.5"></i>
                                    </button>
                                    <button @click="deletePreference(pref.id)" class="p-1.5 text-gray-400 hover:text-red-500 rounded transition-colors">
                                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </template>
                    <div x-show="preferences.length === 0" class="text-center py-12 text-gray-400">
                        <i data-lucide="inbox" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                        <p class="text-sm">No preferences yet. Add one or start a coding session.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Add Modal -->
        <div x-show="showAddModal" x-cloak class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showAddModal = false">
            <div class="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl">
                <h2 class="text-lg font-semibold mb-4">Add Preference</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Preference</label>
                        <textarea x-model="newPref.text" rows="3" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500" placeholder="e.g., Use frozen dataclasses for value objects"></textarea>
                    </div>
                    <div class="flex gap-4">
                        <div class="flex-1">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Scope</label>
                            <input type="text" x-model="newPref.scope" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500" placeholder="python">
                        </div>
                        <div class="flex-1">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Repo (optional)</label>
                            <input type="text" x-model="newPref.repo" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500" placeholder="engram">
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Tags (comma-separated)</label>
                        <input type="text" x-model="newPref.tagsStr" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500" placeholder="testing, pytest">
                    </div>
                </div>
                <div class="flex justify-end gap-3 mt-6">
                    <button @click="showAddModal = false" class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">Cancel</button>
                    <button @click="addPreference()" class="bg-engram-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-engram-700 transition-colors">Add</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Chat View -->
    <div x-show="view === 'chat'" x-cloak class="max-w-3xl mx-auto p-6 flex flex-col" style="height: calc(100vh - 57px)">
        <div class="flex-1 overflow-y-auto space-y-4 mb-4" id="chat-messages">
            <template x-for="(msg, i) in chatHistory" :key="i">
                <div :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
                    <div :class="msg.role === 'user' ? 'bg-engram-600 text-white' : 'bg-white border border-gray-200'" class="max-w-[80%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap" x-text="msg.content"></div>
                </div>
            </template>
            <div x-show="chatLoading" class="flex justify-start">
                <div class="bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-400">Thinking...</div>
            </div>
        </div>
        <div class="flex gap-3">
            <input type="text" x-model="chatInput" @keydown.enter="sendChat()" placeholder="Ask the curation agent..." class="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500 focus:border-transparent" :disabled="chatLoading">
            <button @click="sendChat()" :disabled="chatLoading" class="bg-engram-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-engram-700 transition-colors disabled:opacity-50">Send</button>
        </div>
    </div>

    <!-- Settings View -->
    <div x-show="view === 'settings'" x-cloak class="max-w-2xl mx-auto p-6">
        <h2 class="text-lg font-semibold mb-6">Settings</h2>
        <div class="bg-white border border-gray-200 rounded-lg p-6 space-y-6">
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-3">LLM Provider</h3>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Provider</label>
                        <select x-model="settings.llm.provider" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500">
                            <option value="anthropic">Anthropic</option>
                            <option value="openai">OpenAI</option>
                            <option value="ollama">Ollama</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Model</label>
                        <input type="text" x-model="settings.llm.model" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500">
                    </div>
                </div>
                <div class="mt-3 flex items-center gap-2">
                    <span class="text-xs" :class="settings.llm.has_api_key ? 'text-green-600' : 'text-red-500'" x-text="settings.llm.has_api_key ? 'API key configured' : 'API key missing'"></span>
                </div>
            </div>
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-3">Embedder</h3>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Provider</label>
                        <input type="text" x-model="settings.embedder.provider" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500" readonly>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">Model</label>
                        <input type="text" x-model="settings.embedder.model" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-engram-500" readonly>
                    </div>
                </div>
            </div>
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-3">Storage</h3>
                <p class="text-sm text-gray-500" x-text="settings.storage.path"></p>
            </div>
        </div>
    </div>

    <script>
        function engram() {
            return {
                view: 'preferences',
                preferences: [],
                scopes: [],
                tags: [],
                searchQuery: '',
                filterScope: null,
                filterTags: [],
                showAddModal: false,
                editingId: null,
                editText: '',
                newPref: { text: '', scope: 'global', repo: '', tagsStr: '' },
                chatHistory: [],
                chatInput: '',
                chatLoading: false,
                settings: { llm: {}, embedder: {}, storage: {} },

                async init() {
                    await this.loadPreferences();
                    await this.loadScopes();
                    await this.loadTags();
                    await this.loadSettings();
                    this.$nextTick(() => lucide.createIcons());
                },

                async loadPreferences() {
                    let url = '/api/preferences?';
                    if (this.searchQuery) url += `q=${encodeURIComponent(this.searchQuery)}&`;
                    if (this.filterScope) url += `scope=${this.filterScope}&`;
                    if (this.filterTags.length) url += `tags=${this.filterTags.join(',')}&`;
                    const res = await fetch(url);
                    this.preferences = await res.json();
                    this.$nextTick(() => lucide.createIcons());
                },

                async loadScopes() {
                    const res = await fetch('/api/scopes');
                    this.scopes = await res.json();
                },

                async loadTags() {
                    const res = await fetch('/api/tags');
                    this.tags = await res.json();
                },

                async loadSettings() {
                    const res = await fetch('/api/config');
                    this.settings = await res.json();
                },

                toggleTag(tag) {
                    const idx = this.filterTags.indexOf(tag);
                    if (idx >= 0) this.filterTags.splice(idx, 1);
                    else this.filterTags.push(tag);
                },

                async addPreference() {
                    const tags = this.newPref.tagsStr
                        ? this.newPref.tagsStr.split(',').map(t => t.trim()).filter(Boolean)
                        : [];
                    await fetch('/api/preferences', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            text: this.newPref.text,
                            scope: this.newPref.scope,
                            repo: this.newPref.repo || null,
                            tags: tags,
                        }),
                    });
                    this.showAddModal = false;
                    this.newPref = { text: '', scope: 'global', repo: '', tagsStr: '' };
                    await this.loadPreferences();
                    await this.loadScopes();
                    await this.loadTags();
                },

                startEdit(pref) {
                    this.editingId = pref.id;
                    this.editText = pref.text;
                },

                async saveEdit(id) {
                    await fetch(`/api/preferences/${id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: this.editText }),
                    });
                    this.editingId = null;
                    await this.loadPreferences();
                },

                async deletePreference(id) {
                    if (!confirm('Delete this preference?')) return;
                    await fetch(`/api/preferences/${id}`, { method: 'DELETE' });
                    await this.loadPreferences();
                    await this.loadScopes();
                    await this.loadTags();
                },

                async sendChat() {
                    if (!this.chatInput.trim() || this.chatLoading) return;
                    const message = this.chatInput;
                    this.chatInput = '';
                    this.chatHistory.push({ role: 'user', content: message });
                    this.chatLoading = true;

                    try {
                        const res = await fetch('/api/chat', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                message: message,
                                history: this.chatHistory.slice(0, -1),
                            }),
                        });
                        const text = await res.text();
                        this.chatHistory.push({ role: 'assistant', content: text });
                    } catch (e) {
                        this.chatHistory.push({ role: 'assistant', content: 'Error: Could not reach the server.' });
                    }

                    this.chatLoading = false;
                    this.$nextTick(() => {
                        const el = document.getElementById('chat-messages');
                        if (el) el.scrollTop = el.scrollHeight;
                    });
                },
            };
        }
    </script>
</body>
</html>
```

- [ ] **Step 2: Verify UI serves correctly**

Run: `uv run uvicorn engram.server:app --host 0.0.0.0 --port 3000`
Then open `http://localhost:3000` in a browser.
Expected: The UI loads with navigation, empty preferences list, chat tab, and settings tab.

- [ ] **Step 3: Commit**

```bash
git add ui/index.html
git commit -m "feat: web UI with preferences browser, chat panel, and settings"
```

---

### Task 8: Integration Testing & Polish

**Files:**
- Modify: `src/engram/logging.py` — fix missing import
- Create: `tests/test_integration.py`

- [ ] **Step 1: Fix logging.py import**

In `src/engram/logging.py`, add `import logging.handlers` at the top (after `import logging`), since `RotatingFileHandler` is in the `logging.handlers` submodule.

- [ ] **Step 2: Write integration test**

`tests/test_integration.py`:

```python
"""Integration tests — full stack with real Mem0 (requires API key)."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from engram.models import EngramConfig, StorageConfig, EmbedderConfig, LLMConfig, ServerConfig, LoggingConfig
from engram.server import create_app


needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def integration_config(tmp_path):
    return EngramConfig(
        server=ServerConfig(host="127.0.0.1", port=3099),
        storage=StorageConfig(path=str(tmp_path / "data")),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
        llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
        logging=LoggingConfig(level="DEBUG"),
    )


@pytest.fixture
def integration_app(integration_config):
    return create_app(config=integration_config)


@pytest.fixture
async def integration_client(integration_app):
    transport = ASGITransport(app=integration_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@needs_api_key
async def test_full_preference_lifecycle(integration_client):
    """Test add → list → search → update → inject → delete."""
    client = integration_client

    # Health check
    res = await client.get("/api/health")
    assert res.status_code == 200

    # Add a preference
    res = await client.post("/api/preferences", json={
        "text": "Always use type annotations in function signatures",
        "scope": "python",
        "tags": ["typing"],
    })
    assert res.status_code == 201
    pref = res.json()
    pref_id = pref["id"]
    assert pref["scope"] == "python"

    # List preferences
    res = await client.get("/api/preferences?scope=python")
    assert res.status_code == 200
    prefs = res.json()
    assert len(prefs) >= 1

    # Search
    res = await client.get("/api/preferences?q=type annotations")
    assert res.status_code == 200
    results = res.json()
    assert len(results) >= 1

    # Inject
    res = await client.get("/api/inject?scopes=python,global")
    assert res.status_code == 200
    assert "type annotations" in res.text
    assert "<!-- engram:start -->" in res.text

    # Update
    res = await client.put(f"/api/preferences/{pref_id}", json={
        "text": "Always use type annotations on all public function signatures",
    })
    assert res.status_code == 200

    # Delete
    res = await client.delete(f"/api/preferences/{pref_id}")
    assert res.status_code == 204

    # Verify deletion
    res = await client.get("/api/preferences?scope=python")
    assert not any(p["id"] == pref_id for p in res.json())
```

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: Unit tests pass always. Integration test passes with API key, skipped without.

- [ ] **Step 4: Run full check**

Run: `just check`
Expected: Lint, typecheck, and tests all pass.

- [ ] **Step 5: Commit**

```bash
git add src/engram/logging.py tests/test_integration.py
git commit -m "feat: integration tests and logging fix"
```

---

### Task 9: README and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
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
open http://localhost:3000
```

## How It Works

1. **During coding sessions** — when you give feedback like "don't mock the database" or "use frozen dataclasses", Claude Code stores it via the engram MCP server
2. **Between sessions** — engram deduplicates, resolves conflicts, and organizes preferences using semantic search and LLM-driven analysis
3. **At session start** — a Claude Code hook injects relevant preferences into your CLAUDE.md, scoped to the project's languages and repo

## Setup

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/)
- An Anthropic API key (set as `ANTHROPIC_API_KEY` environment variable)

### Installation

```bash
# Clone and install
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
      "url": "http://localhost:3000/mcp"
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

Open `http://localhost:3000` to:

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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: comprehensive README with setup, usage, and architecture"
```

---

### Summary of Tasks

| Task | What it produces | Dependencies |
|---|---|---|
| 1. Project Scaffolding | pyproject.toml, config, justfile, models, logging | None |
| 2. Memory Layer | memory.py + tests | Task 1 |
| 3. REST API Server | server.py + tests | Tasks 1, 2 |
| 4. MCP Integration | mcp.py, server mount | Tasks 1, 2, 3 |
| 5. Session Injector | injector.py + tests | Tasks 1, 2, 3 |
| 6. Curation Agent | curator.py + tests, chat endpoint | Tasks 1, 2, 3 |
| 7. Web UI | index.html | Tasks 1, 3 |
| 8. Integration Testing | integration tests, polish | Tasks 1–7 |
| 9. README | Documentation | Tasks 1–8 |
