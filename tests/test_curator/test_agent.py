"""Tests for CurationAgent orchestration."""

from engram.curator.agent import CurationAgent, build_system_prompt, build_tool_definitions
from engram.core.models import Confidence, Preference, Source
from engram.llm.base import Message, StopEvent, TextDelta, ToolUse
from engram.storage.memory import InMemoryPreferenceStore
from tests.fakes import FakeLLMClient


def _make_preference(text: str = "Use type hints", scope: str = "python") -> Preference:
    return Preference(
        id="test-id",
        text=text,
        scope=scope,
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )


def test_build_system_prompt_with_prefs() -> None:
    prefs = [_make_preference()]
    prompt = build_system_prompt(prefs)
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
    assert names == {"add_preference", "search_preferences", "update_preference", "delete_preference", "list_preferences"}


async def test_chat_text_response() -> None:
    store = InMemoryPreferenceStore()
    fake_llm = FakeLLMClient(responses=[
        [TextDelta(text="Hello "), TextDelta(text="there!"), StopEvent(reason="end_turn")],
    ])
    agent = CurationAgent(llm=fake_llm, store=store)
    chunks: list[str] = []
    async for chunk in agent.chat("Hi"):
        chunks.append(chunk)
    assert "".join(chunks) == "Hello there!"


async def test_chat_tool_use_adds_preference() -> None:
    store = InMemoryPreferenceStore()
    fake_llm = FakeLLMClient(responses=[
        # Round 1: LLM calls add_preference tool
        [
            ToolUse(
                id="call-1",
                name="add_preference",
                arguments={"text": "Use frozen dataclasses", "scope": "python"},
            ),
            StopEvent(reason="tool_use"),
        ],
        # Round 2: LLM responds with text after tool result
        [TextDelta(text="Saved!"), StopEvent(reason="end_turn")],
    ])
    agent = CurationAgent(llm=fake_llm, store=store)
    chunks: list[str] = []
    async for chunk in agent.chat("Remember: use frozen dataclasses"):
        chunks.append(chunk)
    assert "Saved!" in "".join(chunks)
    # Verify the preference was stored
    all_prefs = await store.get_all()
    assert len(all_prefs) == 1
    assert all_prefs[0].text == "Use frozen dataclasses"


async def test_chat_tool_use_deletes_preference() -> None:
    store = InMemoryPreferenceStore()
    from engram.core.models import PreferenceCreate
    added = await store.add(PreferenceCreate(text="Old pref", scope="python"))

    fake_llm = FakeLLMClient(responses=[
        [
            ToolUse(id="call-1", name="delete_preference", arguments={"id": added.id}),
            StopEvent(reason="tool_use"),
        ],
        [TextDelta(text="Deleted."), StopEvent(reason="end_turn")],
    ])
    agent = CurationAgent(llm=fake_llm, store=store)
    async for _ in agent.chat("Delete that pref"):
        pass
    assert await store.get_all() == []
