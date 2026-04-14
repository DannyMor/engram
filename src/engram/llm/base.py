"""LLM client protocol — async streaming interface for language model interaction."""

from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter]


# --- Stream Events (discriminated union) ---


class TextDelta(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolUse(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    arguments: dict[str, Any]


class StopEvent(BaseModel):
    type: Literal["stop"] = "stop"
    reason: Literal["end_turn", "tool_use"]


StreamEvent = Annotated[
    TextDelta | ToolUse | StopEvent,
    Field(discriminator="type"),
]


class LLMClient(Protocol):
    """Async streaming LLM client."""

    async def stream(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamEvent]: ...
