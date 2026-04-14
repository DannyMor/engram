"""Tests for curator tool command deserialization and dispatch."""

import pytest
from pydantic import ValidationError

from engram.core.models import PreferenceCreate, Source
from engram.curator.tools import (
    AddPreferenceCommand,
    DeletePreferenceCommand,
    ListPreferencesCommand,
    SearchPreferencesCommand,
    ToolCommand,
    UpdatePreferenceCommand,
)


def test_deserialize_add_preference() -> None:
    raw = {"name": "add_preference", "text": "Use type hints", "scope": "python"}
    cmd = AddPreferenceCommand.model_validate(raw)
    assert cmd.text == "Use type hints"
    assert cmd.scope == "python"
    assert cmd.tags == []


def test_deserialize_via_discriminated_union() -> None:
    raw = {"name": "delete_preference", "id": "abc-123"}
    from pydantic import TypeAdapter

    adapter = TypeAdapter(ToolCommand)
    cmd = adapter.validate_python(raw)
    assert isinstance(cmd, DeletePreferenceCommand)
    assert cmd.id == "abc-123"


def test_invalid_command_name_rejected() -> None:
    from pydantic import TypeAdapter

    adapter = TypeAdapter(ToolCommand)
    with pytest.raises(ValidationError):
        adapter.validate_python({"name": "unknown_tool", "text": "foo"})


def test_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        AddPreferenceCommand.model_validate({"name": "add_preference"})


def test_search_preferences_command() -> None:
    raw = {"name": "search_preferences", "query": "dataclass", "scope": "python"}
    cmd = SearchPreferencesCommand.model_validate(raw)
    assert cmd.query == "dataclass"
    assert cmd.scope == "python"


def test_update_preference_command() -> None:
    raw = {"name": "update_preference", "id": "abc", "text": "new text", "tags": ["a", "b"]}
    cmd = UpdatePreferenceCommand.model_validate(raw)
    assert cmd.id == "abc"
    assert cmd.text == "new text"
    assert cmd.tags == ["a", "b"]


def test_list_preferences_command_defaults() -> None:
    raw = {"name": "list_preferences"}
    cmd = ListPreferencesCommand.model_validate(raw)
    assert cmd.scope is None
