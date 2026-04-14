"""Bedrock LLM client — uses AsyncAnthropicBedrock with AWS SSO/profile."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from engram.core.models import BedrockLLMConfig, ProfileAuth, StaticAuth
from engram.llm.anthropic import _to_anthropic_tool
from engram.llm.base import (
    Message,
    StopEvent,
    StreamEvent,
    TextDelta,
    ToolDefinition,
    ToolUse,
)

logger = logging.getLogger(__name__)


class BedrockLLMClient:
    """LLMClient backed by AWS Bedrock."""

    def __init__(self, config: BedrockLLMConfig) -> None:
        match config.aws_auth:
            case ProfileAuth(profile=p, region=r):
                self._client = anthropic.AsyncAnthropicBedrock(
                    aws_profile=p,
                    aws_region=r,
                )
            case StaticAuth(access_key_id=k, secret_access_key=s, session_token=t, region=r):
                self._client = anthropic.AsyncAnthropicBedrock(
                    aws_access_key=k,
                    aws_secret_key=s,
                    aws_session_token=t,
                    aws_region=r,
                )
            case None:
                self._client = anthropic.AsyncAnthropicBedrock()
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
