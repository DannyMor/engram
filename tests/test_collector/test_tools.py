"""Tests for collector tool command deserialization and dispatch."""

import pytest
from pydantic import ValidationError

from engram.collector.tools import (
    AddImprintCommand,
    DeleteImprintCommand,
    ListImprintsCommand,
    SearchImprintsCommand,
    ToolCommand,
    UpdateImprintCommand,
)


def test_deserialize_add_imprint() -> None:
    raw = {"name": "add_imprint", "text": "Use type hints", "scope": "python"}
    cmd = AddImprintCommand.model_validate(raw)
    assert cmd.text == "Use type hints"
    assert cmd.scope == "python"
    assert cmd.tags == []


def test_deserialize_via_discriminated_union() -> None:
    raw = {"name": "delete_imprint", "id": "abc-123"}
    from pydantic import TypeAdapter

    adapter = TypeAdapter(ToolCommand)
    cmd = adapter.validate_python(raw)
    assert isinstance(cmd, DeleteImprintCommand)
    assert cmd.id == "abc-123"


def test_invalid_command_name_rejected() -> None:
    from pydantic import TypeAdapter

    adapter = TypeAdapter(ToolCommand)
    with pytest.raises(ValidationError):
        adapter.validate_python({"name": "unknown_tool", "text": "foo"})


def test_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        AddImprintCommand.model_validate({"name": "add_imprint"})


def test_search_imprints_command() -> None:
    raw = {"name": "search_imprints", "query": "dataclass", "scope": "python"}
    cmd = SearchImprintsCommand.model_validate(raw)
    assert cmd.query == "dataclass"
    assert cmd.scope == "python"


def test_update_imprint_command() -> None:
    raw = {"name": "update_imprint", "id": "abc", "text": "new text", "tags": ["a", "b"]}
    cmd = UpdateImprintCommand.model_validate(raw)
    assert cmd.id == "abc"
    assert cmd.text == "new text"
    assert cmd.tags == ["a", "b"]


def test_list_imprints_command_defaults() -> None:
    raw = {"name": "list_imprints"}
    cmd = ListImprintsCommand.model_validate(raw)
    assert cmd.scope is None
