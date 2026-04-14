"""Curation agent — LLM-powered preference management with typed tool dispatch."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import TypeAdapter

from engram.core.models import Preference, PreferenceCreate, Source
from engram.curator.tools import (
    AddPreferenceCommand,
    DeletePreferenceCommand,
    ListPreferencesCommand,
    SearchPreferencesCommand,
    ToolCommand,
    UpdatePreferenceCommand,
)
from engram.llm.base import (
    LLMClient,
    Message,
    StopEvent,
    StreamEvent,
    TextDelta,
    ToolDefinition,
    ToolParameter,
    ToolUse,
)
from engram.storage.base import PreferenceStore

logger = logging.getLogger(__name__)

_tool_command_adapter = TypeAdapter(ToolCommand)


def build_system_prompt(prefs: list[Preference]) -> str:
    """Build the system prompt for the curation agent."""
    lines = [
        "You are a coding preference curator. You help users manage their coding preferences.",
        "You have tools to add, search, update, delete, and list preferences.",
        "",
        "Current preferences:",
    ]
    if prefs:
        for p in prefs:
            tags_str = f" [{', '.join(p.tags)}]" if p.tags else ""
            lines.append(f"- [{p.scope}]{tags_str} {p.text} (id: {p.id})")
    else:
        lines.append("- (none)")
    return "\n".join(lines)


def build_tool_definitions() -> list[ToolDefinition]:
    """Build typed tool definitions for the LLM."""
    return [
        ToolDefinition(
            name="add_preference",
            description="Store a new coding preference.",
            parameters=[
                ToolParameter(name="text", type="string", description="The preference text"),
                ToolParameter(name="scope", type="string", description="Language or framework scope"),
                ToolParameter(name="repo", type="string", description="Repository name", required=False),
                ToolParameter(name="tags", type="array", description="Categorization tags", required=False),
            ],
        ),
        ToolDefinition(
            name="search_preferences",
            description="Semantic search across preferences.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query"),
                ToolParameter(name="scope", type="string", description="Filter by scope", required=False),
                ToolParameter(name="repo", type="string", description="Filter by repo", required=False),
            ],
        ),
        ToolDefinition(
            name="update_preference",
            description="Update an existing preference.",
            parameters=[
                ToolParameter(name="id", type="string", description="Preference ID to update"),
                ToolParameter(name="text", type="string", description="New text", required=False),
                ToolParameter(name="scope", type="string", description="New scope", required=False),
                ToolParameter(name="tags", type="array", description="New tags", required=False),
            ],
        ),
        ToolDefinition(
            name="delete_preference",
            description="Permanently delete a preference.",
            parameters=[
                ToolParameter(name="id", type="string", description="Preference ID to delete"),
            ],
        ),
        ToolDefinition(
            name="list_preferences",
            description="List all preferences, optionally filtered by scope.",
            parameters=[
                ToolParameter(name="scope", type="string", description="Filter by scope", required=False),
            ],
        ),
    ]


class CurationAgent:
    """Orchestrates LLM tool-use loop for preference curation."""

    def __init__(self, llm: LLMClient, store: PreferenceStore) -> None:
        self._llm = llm
        self._store = store

    async def chat(
        self, message: str, history: list[Message] | None = None
    ) -> AsyncGenerator[str]:
        """Stream a curation response, executing tool calls as needed."""
        all_prefs = await self._store.get_all()
        system = build_system_prompt(all_prefs)
        tools = build_tool_definitions()

        messages: list[Message] = list(history or [])
        messages.append({"role": "user", "content": message})

        max_rounds = 10
        for _ in range(max_rounds):
            pending_tool_uses: list[ToolUse] = []
            stop_reason: str = "end_turn"

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

            if stop_reason != "tool_use" or not pending_tool_uses:
                return

            # Execute tool calls and build tool results
            tool_result_content: list[dict[str, Any]] = []
            for tool_use in pending_tool_uses:
                result = await self._execute_tool(tool_use.name, tool_use.arguments)
                match result:
                    case str() as text:
                        content = text
                    case list() | dict():
                        content = json.dumps(result, default=str)
                    case None:
                        content = '{"status": "ok"}'
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": content,
                })

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
            case AddPreferenceCommand(text=text, scope=scope, repo=repo, tags=tags):
                pref = PreferenceCreate(
                    text=text, scope=scope, repo=repo, tags=tags, source=Source.CURATION_AGENT
                )
                result = await self._store.add(pref)
                return result.model_dump(mode="json")
            case SearchPreferencesCommand(query=query, scope=scope, repo=repo):
                results = await self._store.search(query, scope=scope, repo=repo)
                return [r.model_dump(mode="json") for r in results]
            case UpdatePreferenceCommand(id=preference_id, text=text, scope=scope, tags=tags):
                result = await self._store.update(preference_id, text=text, scope=scope, tags=tags)
                return result.model_dump(mode="json")
            case DeletePreferenceCommand(id=preference_id):
                await self._store.delete(preference_id)
                return None
            case ListPreferencesCommand(scope=scope):
                results = await self._store.get_all(scope=scope)
                return [r.model_dump(mode="json") for r in results]
