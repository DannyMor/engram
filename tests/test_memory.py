"""Tests for the memory layer."""

import os

import pytest

from engram.memory import MemoryStore
from engram.models import (
    EmbedderConfig,
    EngramConfig,
    LLMConfig,
    PreferenceCreate,
    Source,
    StorageConfig,
)

needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def memory_store(tmp_path):
    """Create a MemoryStore with temporary storage."""
    config = EngramConfig(
        storage=StorageConfig(path=str(tmp_path / "data")),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
        llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
    )
    return MemoryStore(config)


@needs_api_key
def test_add_preference(memory_store):
    pref = PreferenceCreate(
        text="Use pytest fixtures over setup/teardown methods",
        scope="python",
        tags=["testing", "pytest"],
        source=Source.MANUAL,
    )
    result = memory_store.add(pref)
    assert result.id is not None
    assert result.text == pref.text
    assert result.scope == "python"
    assert result.tags == ["testing", "pytest"]


@needs_api_key
def test_add_preference_with_repo(memory_store):
    pref = PreferenceCreate(
        text="Skip type annotations in this legacy codebase",
        scope="python",
        repo="legacy-app",
        tags=["typing"],
        source=Source.CODING_SESSION,
    )
    result = memory_store.add(pref)
    assert result.repo == "legacy-app"


@needs_api_key
def test_get_all_preferences(memory_store):
    memory_store.add(PreferenceCreate(text="Use dataclasses", scope="python"))
    memory_store.add(PreferenceCreate(text="Prefer const", scope="typescript"))

    all_prefs = memory_store.get_all()
    assert len(all_prefs) == 2

    python_prefs = memory_store.get_all(scope="python")
    assert len(python_prefs) == 1
    assert python_prefs[0].scope == "python"


@needs_api_key
def test_get_all_with_repo_filter(memory_store):
    memory_store.add(PreferenceCreate(text="Use strict types", scope="python", repo="engram"))
    memory_store.add(PreferenceCreate(text="Skip types", scope="python", repo="legacy"))
    memory_store.add(PreferenceCreate(text="Always lint", scope="python"))

    engram_prefs = memory_store.get_all(scope="python", repo="engram")
    # Should return repo-specific + universal (repo=None)
    assert len(engram_prefs) == 2
    texts = {p.text for p in engram_prefs}
    assert "Use strict types" in texts
    assert "Always lint" in texts
    assert "Skip types" not in texts


@needs_api_key
def test_search_preferences(memory_store):
    memory_store.add(PreferenceCreate(text="Use pytest fixtures for test setup", scope="python"))
    memory_store.add(PreferenceCreate(text="Prefer functional components in React", scope="react"))

    results = memory_store.search("testing setup", scope="python")
    assert len(results) >= 1
    assert any("pytest" in r.text.lower() or "test" in r.text.lower() for r in results)


@needs_api_key
def test_delete_preference(memory_store):
    pref = memory_store.add(PreferenceCreate(text="Temporary pref", scope="global"))
    memory_store.delete(pref.id)

    all_prefs = memory_store.get_all()
    assert not any(p.id == pref.id for p in all_prefs)


@needs_api_key
def test_update_preference(memory_store):
    pref = memory_store.add(PreferenceCreate(text="Use dicts", scope="python"))
    updated = memory_store.update(pref.id, text="Use dataclasses instead of dicts")
    assert updated.text == "Use dataclasses instead of dicts"
    assert updated.id == pref.id
