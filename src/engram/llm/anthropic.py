"""Anthropic LLM client — uses AsyncAnthropic with direct API key."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from engram.core.config import resolve_api_key
from engram.core.models import AnthropicLLMConfig
from engram.llm.base import (
    Message,
    StopEvent,
    StreamEvent,
    TextDelta,
    ToolDefinition,
    ToolUse,
)

logger = logging.getLogger(__name__)


class AnthropicLLMClient:
    """LLMClient backed by the Anthropic API."""

    def __init__(self, config: AnthropicLLMConfig) -> None:
        api_key = resolve_api_key(config.api_key_env)
        if not api_key:
            raise ValueError(f"API key not found in env var {config.api_key_env}")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = config.model

    async def stream(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 2048,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [_to_anthropic_tool(t) for t in tools]

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                match event.type:
                    case "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield TextDelta(text=event.delta.text)
                    case "content_block_stop":
                        block = stream.current_message_snapshot.content[event.index]
                        if block.type == "tool_use":
                            yield ToolUse(
                                id=block.id,
                                name=block.name,
                                arguments=dict(block.input) if block.input else {},
                            )
                    case "message_stop":
                        stop_reason = stream.current_message_snapshot.stop_reason or "end_turn"
                        yield StopEvent(reason=stop_reason)


def _to_anthropic_tool(tool: ToolDefinition) -> dict[str, Any]:
    """Convert ToolDefinition to Anthropic API tool format."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in tool.parameters:
        properties[param.name] = {
            "type": param.type,
            "description": param.description,
        }
        if param.required:
            required.append(param.name)
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }
