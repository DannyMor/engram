"""Tests for ImprintCollector orchestration."""

from engram.collector.agent import ImprintCollector, build_system_prompt, build_tool_definitions
from engram.core.models import Confidence, Imprint, Source
from engram.llm.base import StopEvent, TextDelta, ToolUse
from engram.storage.memory import InMemoryImprintStore
from tests.fakes import FakeLLMClient


def _make_imprint(text: str = "Use type hints", scope: str = "python") -> Imprint:
    return Imprint(
        id="test-id",
        text=text,
        scope=scope,
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )


def test_build_system_prompt_with_imprints() -> None:
    imprints = [_make_imprint()]
    prompt = build_system_prompt(imprints)
    assert "Use type hints" in prompt
    assert "[python]" in prompt
    assert "test-id" in prompt


def test_build_system_prompt_empty() -> None:
    prompt = build_system_prompt([])
    assert "(none)" in prompt


def test_build_tool_definitions_returns_typed() -> None:
    tools = build_tool_definitions()
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert names == {
        "add_imprint",
        "search_imprints",
        "update_imprint",
        "delete_imprint",
        "list_imprints",
    }


async def test_chat_text_response() -> None:
    store = InMemoryImprintStore()
    fake_llm = FakeLLMClient(
        responses=[
            [TextDelta(text="Hello "), TextDelta(text="there!"), StopEvent(reason="end_turn")],
        ]
    )
    collector = ImprintCollector(llm=fake_llm, store=store)
    chunks: list[str] = []
    async for chunk in collector.chat("Hi"):
        chunks.append(chunk)
    assert "".join(chunks) == "Hello there!"


async def test_chat_tool_use_adds_imprint() -> None:
    store = InMemoryImprintStore()
    fake_llm = FakeLLMClient(
        responses=[
            # Round 1: LLM calls add_imprint tool
            [
                ToolUse(
                    id="call-1",
                    name="add_imprint",
                    arguments={"text": "Use frozen dataclasses", "scope": "python"},
                ),
                StopEvent(reason="tool_use"),
            ],
            # Round 2: LLM responds with text after tool result
            [TextDelta(text="Saved!"), StopEvent(reason="end_turn")],
        ]
    )
    collector = ImprintCollector(llm=fake_llm, store=store)
    chunks: list[str] = []
    async for chunk in collector.chat("Remember: use frozen dataclasses"):
        chunks.append(chunk)
    assert "Saved!" in "".join(chunks)
    # Verify the imprint was stored
    all_imprints = await store.get_all()
    assert len(all_imprints) == 1
    assert all_imprints[0].text == "Use frozen dataclasses"


async def test_chat_tool_use_deletes_imprint() -> None:
    store = InMemoryImprintStore()
    from engram.core.models import ImprintCreate

    added = await store.add(ImprintCreate(text="Old imprint", scope="python"))

    fake_llm = FakeLLMClient(
        responses=[
            [
                ToolUse(id="call-1", name="delete_imprint", arguments={"id": added.id}),
                StopEvent(reason="tool_use"),
            ],
            [TextDelta(text="Deleted."), StopEvent(reason="end_turn")],
        ]
    )
    collector = ImprintCollector(llm=fake_llm, store=store)
    async for _ in collector.chat("Delete that imprint"):
        pass
    assert await store.get_all() == []
