"""Curation agent — LLM-powered preference management with tool use."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import anthropic
from anthropic.types import MessageParam, ToolParam

from engram.config import resolve_api_key
from engram.models import Preference, PreferenceCreate, Source

if TYPE_CHECKING:
    from engram.memory import MemoryStore
    from engram.models import ChatMessage, EngramConfig

logger = logging.getLogger(__name__)


def build_system_prompt(prefs: list[Preference]) -> str:
    """Build a system prompt that includes all current preferences."""
    intro = (
        "You are a preference management assistant for engram. "
        "Your role is to help users add, search, update, delete, analyze, "
        "and suggest coding preferences. "
        "You have access to tools that interact with the preference store.\n\n"
    )

    if not prefs:
        return intro + "There are currently no preferences stored."

    lines = ["Current stored preferences:\n"]
    for p in prefs:
        tags = ", ".join(p.tags) if p.tags else "none"
        lines.append(
            f"- [{p.scope}] {p.text} (id={p.id}, tags={tags}, "
            f"source={p.source}, confidence={p.confidence})"
        )

    return intro + "\n".join(lines)


def build_tool_definitions() -> list[dict[str, Any]]:
    """Return Anthropic API-compatible tool definitions for preference management."""
    return [
        {
            "name": "add_preference",
            "description": "Add a new coding preference to the store.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The preference text.",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Scope for the preference (e.g. 'python', 'global').",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Optional repository name.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorisation.",
                    },
                },
                "required": ["text", "scope"],
            },
        },
        {
            "name": "search_preferences",
            "description": "Semantic search for preferences matching a query.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional scope filter.",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Optional repository filter.",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_preferences",
            "description": "List all preferences, optionally filtered by scope, repo, or tags.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Optional scope filter.",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Optional repository filter.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tag filter.",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "delete_preference",
            "description": "Delete a preference by its ID.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "preference_id": {
                        "type": "string",
                        "description": "The ID of the preference to delete.",
                    },
                },
                "required": ["preference_id"],
            },
        },
        {
            "name": "update_preference",
            "description": "Update an existing preference by its ID.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "preference_id": {
                        "type": "string",
                        "description": "The ID of the preference to update.",
                    },
                    "text": {
                        "type": "string",
                        "description": "New preference text.",
                    },
                    "scope": {
                        "type": "string",
                        "description": "New scope.",
                    },
                    "repo": {
                        "type": "string",
                        "description": "New repository.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New tags.",
                    },
                },
                "required": ["preference_id"],
            },
        },
    ]


class CurationAgent:
    """LLM-powered agent that manages preferences via tool use."""

    def __init__(self, config: EngramConfig, memory_store: MemoryStore) -> None:
        api_key = resolve_api_key(config.llm.api_key_env)
        if not api_key:
            raise ValueError(
                f"API key not found. Set {config.llm.api_key_env} environment variable."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = config.llm.model
        self._memory = memory_store

    async def chat(
        self, message: str, history: list[ChatMessage]
    ) -> AsyncGenerator[str]:
        """Send a message to the LLM and yield text chunks, handling tool use."""
        all_prefs = self._memory.get_all()
        system_prompt = build_system_prompt(all_prefs)
        tools: list[ToolParam] = [
            ToolParam(
                name=t["name"],
                description=t["description"],
                input_schema=t["input_schema"],
            )
            for t in build_tool_definitions()
        ]

        messages: list[MessageParam] = [
            {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
            for m in history
        ]
        messages.append({"role": "user", "content": message})

        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            # Check if response contains tool use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # Text-only response — yield text chunks
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            # Process tool calls: add assistant response, then each tool result
            messages.append(
                {"role": "assistant", "content": response.content},  # type: ignore[typeddict-item]
            )

            tool_results: list[dict[str, Any]] = []
            for tool_block in tool_use_blocks:
                result = self._execute_tool(tool_block.name, tool_block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": (
                            json.dumps(result) if not isinstance(result, str) else result
                        ),
                    }
                )

            messages.append(
                {"role": "user", "content": tool_results},  # type: ignore[typeddict-item]
            )

            # Also yield any text blocks interleaved with tool calls
            for block in response.content:
                if block.type == "text" and block.text:
                    yield block.text

    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict | list | str:
        """Dispatch a tool call to the appropriate memory store method."""
        if name == "add_preference":
            pref = self._memory.add(
                PreferenceCreate(
                    text=args["text"],
                    scope=args["scope"],
                    repo=args.get("repo"),
                    tags=args.get("tags", []),
                    source=Source.CURATION_AGENT,
                )
            )
            return pref.model_dump(mode="json")

        if name == "search_preferences":
            prefs = self._memory.search(
                query=args["query"],
                scope=args.get("scope"),
                repo=args.get("repo"),
            )
            return [p.model_dump(mode="json") for p in prefs]

        if name == "list_preferences":
            prefs = self._memory.get_all(
                scope=args.get("scope"),
                repo=args.get("repo"),
                tags=args.get("tags"),
            )
            return [p.model_dump(mode="json") for p in prefs]

        if name == "delete_preference":
            self._memory.delete(args["preference_id"])
            return {"status": "deleted", "id": args["preference_id"]}

        if name == "update_preference":
            pref = self._memory.update(
                preference_id=args["preference_id"],
                text=args.get("text"),
                scope=args.get("scope"),
                repo=args.get("repo"),
                tags=args.get("tags"),
            )
            return pref.model_dump(mode="json")

        return {"error": f"Unknown tool: {name}"}
