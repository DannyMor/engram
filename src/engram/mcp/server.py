"""MCP server — exposes preference tools for Claude Code."""

import asyncio
import logging
from typing import Any

from fastmcp import FastMCP

from engram.core.models import PreferenceCreate, Source
from engram.storage.base import PreferenceStore

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Engram is the user's coding preference memory. When the user gives feedback "
    "about how code should be written — coding style, patterns to use or avoid, "
    "testing approaches, naming conventions, architectural preferences — call "
    'add_preference() to store it. Examples: "don\'t mock the database in tests", '
    '"use frozen dataclasses", "prefer composition over inheritance". Do not store '
    "task-specific instructions or one-off corrections. "
    "IMPORTANT: Storing preferences is passive background work — never let it block "
    "or slow down the user's primary task. Call the tool and move on immediately. "
    "At session start, preferences are already loaded into context via CLAUDE.md — "
    "do not call get_preferences_for_context() yourself."
)


async def _store_with_logging(store: PreferenceStore, pref: PreferenceCreate) -> None:
    """Background task for fire-and-forget preference storage."""
    try:
        await store.add(pref)
        logger.info(f"Stored preference: scope={pref.scope} text={pref.text[:80]}")
    except Exception:
        logger.exception(f"Failed to store preference: {pref.text[:80]}")


def create_mcp(store: PreferenceStore) -> FastMCP:
    """Create the MCP server with preference tools."""
    mcp = FastMCP("engram", instructions=INSTRUCTIONS)

    @mcp.tool()
    async def add_preference(
        text: str,
        scope: str,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, str]:
        """Store a coding preference. Called when the user gives feedback about coding style."""
        pref = PreferenceCreate(
            text=text,
            scope=scope,
            repo=repo,
            tags=tags or [],
            source=Source.CODING_SESSION,
        )
        asyncio.create_task(_store_with_logging(store, pref))
        return {"status": "accepted", "text": text, "scope": scope}

    @mcp.tool()
    async def get_preferences_for_context(
        languages: list[str] | None = None,
        repo: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get relevant preferences for the current session context."""
        scopes = ["global"] + (languages or [])
        all_prefs: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for scope in scopes:
            for p in await store.get_all(scope=scope, repo=repo):
                if p.id not in seen_ids:
                    all_prefs.append(p.model_dump(mode="json"))
                    seen_ids.add(p.id)
        logger.info(f"get_preferences_for_context: scopes={scopes} returned {len(all_prefs)}")
        return all_prefs

    @mcp.tool()
    async def search_preferences(
        query: str,
        scope: str | None = None,
        repo: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across all stored preferences."""
        results = await store.search(query, scope=scope, repo=repo)
        logger.info(f"search_preferences: query={query} returned {len(results)}")
        return [r.model_dump(mode="json") for r in results]

    @mcp.tool()
    async def list_preferences(
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List all stored preferences, optionally filtered."""
        results = await store.get_all(scope=scope, repo=repo, tags=tags)
        return [r.model_dump(mode="json") for r in results]

    @mcp.tool()
    async def delete_preference(preference_id: str) -> dict[str, str]:
        """Permanently delete a preference by ID."""
        await store.delete(preference_id)
        logger.info(f"delete_preference: id={preference_id}")
        return {"deleted": preference_id}

    @mcp.tool()
    async def update_preference(
        preference_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing preference."""
        result = await store.update(preference_id, text=text, scope=scope, repo=repo, tags=tags)
        logger.info(f"update_preference: id={preference_id}")
        return result.model_dump(mode="json")

    return mcp
