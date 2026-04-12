"""Tests for the curation agent — prompt building and tool definitions."""

from engram.curator import build_system_prompt, build_tool_definitions
from engram.models import Confidence, Preference, Source


def test_build_system_prompt_with_prefs():
    prefs = [
        Preference(
            id="1",
            text="Use pytest fixtures",
            scope="python",
            tags=["testing"],
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        ),
        Preference(
            id="2",
            text="Prefer composition",
            scope="global",
            tags=[],
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        ),
    ]
    prompt = build_system_prompt(prefs)
    assert "Use pytest fixtures" in prompt
    assert "Prefer composition" in prompt
    assert "python" in prompt
    assert "preference" in prompt.lower()


def test_build_system_prompt_empty():
    prompt = build_system_prompt([])
    lowered = prompt.lower()
    assert "no preferences" in lowered or "empty" in lowered or "none" in lowered


def test_build_tool_definitions():
    tools = build_tool_definitions()
    tool_names = [t["name"] for t in tools]
    assert "add_preference" in tool_names
    assert "search_preferences" in tool_names
    assert "delete_preference" in tool_names
    assert "update_preference" in tool_names
    assert "list_preferences" in tool_names
