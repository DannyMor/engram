"""Fake implementations for testing — no mocks, no external dependencies."""

from collections.abc import AsyncIterator

from engram.llm.base import LLMClient, Message, StreamEvent, ToolDefinition


class FakeLLMClient:
    """LLMClient that yields scripted StreamEvent sequences.

    Usage:
        fake = FakeLLMClient(responses=[
            [TextDelta(text="Hello"), StopEvent(reason="end_turn")],
            [ToolUse(id="1", name="add_preference", arguments={...})],
        ])
    Each call to stream() pops the next response from the list.
    """

    def __init__(self, responses: list[list[StreamEvent]]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def stream(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        if self._call_count >= len(self._responses):
            raise RuntimeError(
                f"FakeLLMClient exhausted: {self._call_count} calls made, "
                f"only {len(self._responses)} responses scripted"
            )
        events = self._responses[self._call_count]
        self._call_count += 1
        for event in events:
            yield event

    @property
    def call_count(self) -> int:
        return self._call_count
