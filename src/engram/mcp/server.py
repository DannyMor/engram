"""MCP server — exposes imprint tools for Claude Code."""

import asyncio
import logging
from typing import Any

from fastmcp import FastMCP

from engram.core.models import ImprintCreate, Source
from engram.storage.base import ImprintStore

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[None]] = set()

INSTRUCTIONS = (
    "Engram is the user's coding imprint memory. When the user gives feedback "
    "about how code should be written — coding style, patterns to use or avoid, "
    "testing approaches, naming conventions, architectural imprints — call "
    'add_imprint() to store it. Examples: "don\'t mock the database in tests", '
    '"use frozen dataclasses", "prefer composition over inheritance". Do not store '
    "task-specific instructions or one-off corrections. "
    "IMPORTANT: Storing imprints is passive background work — never let it block "
    "or slow down the user's primary task. Call the tool and move on immediately. "
    "At session start, imprints are already loaded into context via CLAUDE.md — "
    "do not call get_imprints_for_context() yourself."
)


async def _store_with_logging(store: ImprintStore, imprint: ImprintCreate) -> None:
    """Background task for fire-and-forget imprint storage."""
    try:
        await store.add(imprint)
        logger.info(f"Stored imprint: scope={imprint.scope} text={imprint.text[:80]}")
    except Exception:
        logger.exception(f"Failed to store imprint: {imprint.text[:80]}")


def create_mcp(store: ImprintStore) -> FastMCP:
    """Create the MCP server with imprint tools."""
    mcp = FastMCP("engram", instructions=INSTRUCTIONS)

    @mcp.tool()
    async def add_imprint(
        text: str,
        scope: str,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, str]:
        """Store a coding imprint. Called when the user gives feedback about coding style."""
        imprint = ImprintCreate(
            text=text,
            scope=scope,
            repo=repo,
            tags=tags or [],
            source=Source.CODING_SESSION,
        )
        task = asyncio.create_task(_store_with_logging(store, imprint))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"status": "accepted", "text": text, "scope": scope}

    @mcp.tool()
    async def get_imprints_for_context(
        languages: list[str] | None = None,
        repo: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get relevant imprints for the current session context."""
        scopes = ["global"] + (languages or [])
        all_imprints: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for scope in scopes:
            for i in await store.get_all(scope=scope, repo=repo):
                if i.id not in seen_ids:
                    all_imprints.append(i.model_dump(mode="json"))
                    seen_ids.add(i.id)
        logger.info(f"get_imprints_for_context: scopes={scopes} returned {len(all_imprints)}")
        return all_imprints

    @mcp.tool()
    async def search_imprints(
        query: str,
        scope: str | None = None,
        repo: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across all stored imprints."""
        results = await store.search(query, scope=scope, repo=repo)
        logger.info(f"search_imprints: query={query} returned {len(results)}")
        return [r.model_dump(mode="json") for r in results]

    @mcp.tool()
    async def list_imprints(
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List all stored imprints, optionally filtered."""
        results = await store.get_all(scope=scope, repo=repo, tags=tags)
        return [r.model_dump(mode="json") for r in results]

    @mcp.tool()
    async def delete_imprint(imprint_id: str) -> dict[str, str]:
        """Permanently delete an imprint by ID."""
        await store.delete(imprint_id)
        logger.info(f"delete_imprint: id={imprint_id}")
        return {"deleted": imprint_id}

    @mcp.tool()
    async def update_imprint(
        imprint_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing imprint."""
        result = await store.update(imprint_id, text=text, scope=scope, repo=repo, tags=tags)
        logger.info(f"update_imprint: id={imprint_id}")
        return result.model_dump(mode="json")

    return mcp
