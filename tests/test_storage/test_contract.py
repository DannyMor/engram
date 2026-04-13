"""Contract tests for PreferenceStore implementations.

These tests verify that any PreferenceStore implementation honors the protocol.
Run against InMemoryPreferenceStore by default; integration tests run against Mem0PreferenceStore.
"""

import pytest

from engram.core.models import Preference, PreferenceCreate, Source
from engram.storage.memory import InMemoryPreferenceStore


@pytest.fixture
def store() -> InMemoryPreferenceStore:
    return InMemoryPreferenceStore()


def _make_pref(
    text: str = "Use type annotations",
    scope: str = "python",
    repo: str | None = None,
    tags: list[str] | None = None,
) -> PreferenceCreate:
    return PreferenceCreate(
        text=text,
        scope=scope,
        repo=repo,
        tags=tags or [],
        source=Source.MANUAL,
    )


async def test_add_returns_preference_with_id(store: InMemoryPreferenceStore) -> None:
    pref = await store.add(_make_pref())
    assert isinstance(pref, Preference)
    assert pref.id
    assert pref.text == "Use type annotations"
    assert pref.scope == "python"


async def test_get_returns_added_preference(store: InMemoryPreferenceStore) -> None:
    added = await store.add(_make_pref())
    retrieved = await store.get(added.id)
    assert retrieved.id == added.id
    assert retrieved.text == added.text


async def test_get_nonexistent_raises(store: InMemoryPreferenceStore) -> None:
    with pytest.raises(KeyError):
        await store.get("nonexistent-id")


async def test_get_all_returns_all(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref("Pref A", scope="python"))
    await store.add(_make_pref("Pref B", scope="typescript"))
    all_prefs = await store.get_all()
    assert len(all_prefs) == 2


async def test_get_all_filters_by_scope(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref("Pref A", scope="python"))
    await store.add(_make_pref("Pref B", scope="typescript"))
    python_prefs = await store.get_all(scope="python")
    assert len(python_prefs) == 1
    assert python_prefs[0].scope == "python"


async def test_get_all_filters_by_repo(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref("Pref A", repo="engram"))
    await store.add(_make_pref("Pref B", repo="other"))
    await store.add(_make_pref("Pref C"))
    prefs = await store.get_all(repo="engram")
    assert len(prefs) == 2  # engram + global (no repo)


async def test_get_all_filters_by_tags(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref("Pref A", tags=["typing"]))
    await store.add(_make_pref("Pref B", tags=["testing"]))
    prefs = await store.get_all(tags=["typing"])
    assert len(prefs) == 1
    assert "typing" in prefs[0].tags


async def test_search_finds_matching_text(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref("Use frozen dataclasses"))
    await store.add(_make_pref("Prefer composition over inheritance"))
    results = await store.search("dataclass")
    assert len(results) >= 1
    assert any("dataclass" in r.text.lower() for r in results)


async def test_search_filters_by_scope(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref("Use type annotations", scope="python"))
    await store.add(_make_pref("Use type annotations", scope="typescript"))
    results = await store.search("type annotations", scope="python")
    assert all(r.scope == "python" for r in results)


async def test_update_text(store: InMemoryPreferenceStore) -> None:
    added = await store.add(_make_pref("Old text"))
    updated = await store.update(added.id, text="New text")
    assert updated.text == "New text"
    assert updated.id == added.id


async def test_update_scope(store: InMemoryPreferenceStore) -> None:
    added = await store.add(_make_pref(scope="python"))
    updated = await store.update(added.id, scope="global")
    assert updated.scope == "global"


async def test_update_tags(store: InMemoryPreferenceStore) -> None:
    added = await store.add(_make_pref(tags=["old"]))
    updated = await store.update(added.id, tags=["new", "updated"])
    assert updated.tags == ["new", "updated"]


async def test_update_nonexistent_raises(store: InMemoryPreferenceStore) -> None:
    with pytest.raises(KeyError):
        await store.update("nonexistent-id", text="text")


async def test_delete_removes_preference(store: InMemoryPreferenceStore) -> None:
    added = await store.add(_make_pref())
    await store.delete(added.id)
    with pytest.raises(KeyError):
        await store.get(added.id)


async def test_delete_nonexistent_raises(store: InMemoryPreferenceStore) -> None:
    with pytest.raises(KeyError):
        await store.delete("nonexistent-id")


async def test_get_scopes_returns_distinct(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref(scope="python"))
    await store.add(_make_pref(scope="python"))
    await store.add(_make_pref(scope="typescript"))
    scopes = await store.get_scopes()
    assert sorted(scopes) == ["python", "typescript"]


async def test_get_tags_returns_distinct(store: InMemoryPreferenceStore) -> None:
    await store.add(_make_pref(tags=["typing", "style"]))
    await store.add(_make_pref(tags=["typing", "testing"]))
    tags = await store.get_tags()
    assert sorted(tags) == ["style", "testing", "typing"]
