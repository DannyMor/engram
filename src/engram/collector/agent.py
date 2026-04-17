"""Imprint collector agent — LLM-powered imprint management with typed tool dispatch."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import TypeAdapter

from engram.collector.tools import (
    AddImprintCommand,
    DeleteImprintCommand,
    ListImprintsCommand,
    SearchImprintsCommand,
    ToolCommand,
    UpdateImprintCommand,
)
from engram.core.models import Imprint, ImprintCreate, Source
from engram.llm.base import (
    LLMClient,
    Message,
    StopEvent,
    TextDelta,
    ToolDefinition,
    ToolParameter,
    ToolUse,
)
from engram.storage.base import ImprintStore

logger = logging.getLogger(__name__)

_tool_command_adapter = TypeAdapter(ToolCommand)


def build_system_prompt(imprints: list[Imprint]) -> str:
    """Build the system prompt for the imprint collector."""
    lines = [
        "You are a coding imprint collector. You help users manage their coding imprints.",
        "You have tools to add, search, update, delete, and list imprints.",
        "",
        "Current imprints:",
    ]
    if imprints:
        for i in imprints:
            tags_str = f" [{', '.join(i.tags)}]" if i.tags else ""
            lines.append(f"- [{i.scope}]{tags_str} {i.text} (id: {i.id})")
    else:
        lines.append("- (none)")
    return "\n".join(lines)


def build_tool_definitions() -> list[ToolDefinition]:
    """Build typed tool definitions for the LLM."""
    return [
        ToolDefinition(
            name="add_imprint",
            description="Store a new coding imprint.",
            parameters=[
                ToolParameter(name="text", type="string", description="The imprint text"),
                ToolParameter(
                    name="scope",
                    type="string",
                    description="Language or framework scope",
                ),
                ToolParameter(
                    name="repo",
                    type="string",
                    description="Repository name",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Categorization tags",
                    required=False,
                ),
            ],
        ),
        ToolDefinition(
            name="search_imprints",
            description="Semantic search across imprints.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query"),
                ToolParameter(
                    name="scope",
                    type="string",
                    description="Filter by scope",
                    required=False,
                ),
                ToolParameter(
                    name="repo",
                    type="string",
                    description="Filter by repo",
                    required=False,
                ),
            ],
        ),
        ToolDefinition(
            name="update_imprint",
            description="Update an existing imprint.",
            parameters=[
                ToolParameter(name="id", type="string", description="Imprint ID to update"),
                ToolParameter(name="text", type="string", description="New text", required=False),
                ToolParameter(name="scope", type="string", description="New scope", required=False),
                ToolParameter(name="tags", type="array", description="New tags", required=False),
            ],
        ),
        ToolDefinition(
            name="delete_imprint",
            description="Permanently delete an imprint.",
            parameters=[
                ToolParameter(name="id", type="string", description="Imprint ID to delete"),
            ],
        ),
        ToolDefinition(
            name="list_imprints",
            description="List all imprints, optionally filtered by scope.",
            parameters=[
                ToolParameter(
                    name="scope",
                    type="string",
                    description="Filter by scope",
                    required=False,
                ),
            ],
        ),
    ]


class ImprintCollector:
    """Orchestrates LLM tool-use loop for imprint collection."""

    def __init__(self, llm: LLMClient, store: ImprintStore) -> None:
        self._llm = llm
        self._store = store

    async def chat(self, message: str, history: list[Message] | None = None) -> AsyncGenerator[str]:
        """Stream a collector response, executing tool calls as needed."""
        try:
            all_imprints = await self._store.get_all()
        except Exception:
            logger.exception("Failed to load imprints")
            yield "\n\nError: Could not load imprints."
            return

        system = build_system_prompt(all_imprints)
        tools = build_tool_definitions()

        messages: list[Message] = list(history or [])
        messages.append({"role": "user", "content": message})

        max_rounds = 10
        for _ in range(max_rounds):
            pending_tool_uses: list[ToolUse] = []
            stop_reason: str = "end_turn"

            try:
                async for event in self._llm.stream(
                    messages=messages, system=system, tools=tools
                ):
                    match event:
                        case TextDelta(text=text):
                            yield text
                        case ToolUse() as tool_use:
                            pending_tool_uses.append(tool_use)
                        case StopEvent(reason=reason):
                            stop_reason = reason
            except Exception:
                logger.exception("LLM streaming failed")
                yield "\n\nError: LLM request failed. Check your API key or provider config."
                return

            if stop_reason != "tool_use" or not pending_tool_uses:
                return

            # Execute tool calls and build tool results
            tool_result_content: list[dict[str, Any]] = []
            for tool_use in pending_tool_uses:
                try:
                    result = await self._execute_tool(tool_use.name, tool_use.arguments)
                except Exception:
                    logger.exception("Tool execution failed: %s", tool_use.name)
                    result = {"error": f"Tool '{tool_use.name}' failed unexpectedly"}
                match result:
                    case str() as text:
                        content = text
                    case list() | dict():
                        content = json.dumps(result, default=str)
                    case None:
                        content = '{"status": "ok"}'
                tool_result_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": content,
                    }
                )

            # Append assistant message with tool uses + tool results
            assistant_blocks = [
                {"type": "tool_use", "id": t.id, "name": t.name, "input": t.arguments}
                for t in pending_tool_uses
            ]
            messages.append({"role": "assistant", "content": assistant_blocks})
            messages.append({"role": "user", "content": tool_result_content})

    async def _execute_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | list[dict[str, Any]] | str | None:
        """Deserialize and execute a tool command."""
        try:
            command = _tool_command_adapter.validate_python({"name": name, **arguments})
        except Exception as e:
            return {"error": f"Invalid tool call: {e}"}

        match command:
            case AddImprintCommand(text=text, scope=scope, repo=repo, tags=tags):
                imprint = ImprintCreate(
                    text=text, scope=scope, repo=repo, tags=tags, source=Source.COLLECTOR
                )
                result = await self._store.add(imprint)
                return result.model_dump(mode="json")
            case SearchImprintsCommand(query=query, scope=scope, repo=repo):
                results = await self._store.search(query, scope=scope, repo=repo)
                return [r.model_dump(mode="json") for r in results]
            case UpdateImprintCommand(id=imprint_id, text=text, scope=scope, tags=tags):
                result = await self._store.update(imprint_id, text=text, scope=scope, tags=tags)
                return result.model_dump(mode="json")
            case DeleteImprintCommand(id=imprint_id):
                await self._store.delete(imprint_id)
                return None
            case ListImprintsCommand(scope=scope):
                results = await self._store.get_all(scope=scope)
                return [r.model_dump(mode="json") for r in results]
