"""MCP server — exposes preference tools for Claude Code."""

import logging

from fastmcp import FastMCP

from engram.memory import MemoryStore
from engram.models import PreferenceCreate, Source

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Engram is the user's coding preference memory. When the user gives feedback "
    "about how code should be written — coding style, patterns to use or avoid, "
    "testing approaches, naming conventions, architectural preferences — call "
    'add_preference() to store it. Examples: "don\'t mock the database in tests", '
    '"use frozen dataclasses", "prefer composition over inheritance". Do not store '
    "task-specific instructions or one-off corrections. At session start, preferences "
    "are already loaded into context via CLAUDE.md — do not call "
    "get_preferences_for_context() yourself."
)


def create_mcp(memory_store: MemoryStore) -> FastMCP:
    """Create the MCP server with preference tools."""
    mcp = FastMCP("engram", instructions=DESCRIPTION)

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
        logger.info(
            "MCP add_preference: scope=%s repo=%s text=%s",
            scope,
            repo,
            text[:80],
        )
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
        logger.info(
            "MCP get_preferences_for_context: scopes=%s repo=%s returned %d",
            scopes,
            repo,
            len(all_prefs),
        )
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
        logger.info(
            "MCP search_preferences: query=%s returned %d",
            query[:50],
            len(results),
        )
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
