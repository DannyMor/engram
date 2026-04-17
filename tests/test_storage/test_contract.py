"""Contract tests for ImprintStore implementations.

These tests verify that any ImprintStore implementation honors the protocol.
Run against InMemoryImprintStore by default; integration tests run against Mem0ImprintStore.
"""

import pytest

from engram.core.models import Imprint, ImprintCreate, Source
from engram.storage.memory import InMemoryImprintStore


@pytest.fixture
def store() -> InMemoryImprintStore:
    return InMemoryImprintStore()


def _make_imprint(
    text: str = "Use type annotations",
    scope: str = "python",
    repo: str | None = None,
    tags: list[str] | None = None,
) -> ImprintCreate:
    return ImprintCreate(
        text=text,
        scope=scope,
        repo=repo,
        tags=tags or [],
        source=Source.MANUAL,
    )


async def test_add_returns_imprint_with_id(store: InMemoryImprintStore) -> None:
    imprint = await store.add(_make_imprint())
    assert isinstance(imprint, Imprint)
    assert imprint.id
    assert imprint.text == "Use type annotations"
    assert imprint.scope == "python"


async def test_get_returns_added_imprint(store: InMemoryImprintStore) -> None:
    added = await store.add(_make_imprint())
    retrieved = await store.get(added.id)
    assert retrieved.id == added.id
    assert retrieved.text == added.text


async def test_get_nonexistent_raises(store: InMemoryImprintStore) -> None:
    with pytest.raises(KeyError):
        await store.get("nonexistent-id")


async def test_get_all_returns_all(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint("Imprint A", scope="python"))
    await store.add(_make_imprint("Imprint B", scope="typescript"))
    all_imprints = await store.get_all()
    assert len(all_imprints) == 2


async def test_get_all_filters_by_scope(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint("Imprint A", scope="python"))
    await store.add(_make_imprint("Imprint B", scope="typescript"))
    python_imprints = await store.get_all(scope="python")
    assert len(python_imprints) == 1
    assert python_imprints[0].scope == "python"


async def test_get_all_filters_by_repo(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint("Imprint A", repo="engram"))
    await store.add(_make_imprint("Imprint B", repo="other"))
    await store.add(_make_imprint("Imprint C"))
    imprints = await store.get_all(repo="engram")
    assert len(imprints) == 2  # engram + global (no repo)


async def test_get_all_filters_by_tags(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint("Imprint A", tags=["typing"]))
    await store.add(_make_imprint("Imprint B", tags=["testing"]))
    imprints = await store.get_all(tags=["typing"])
    assert len(imprints) == 1
    assert "typing" in imprints[0].tags


async def test_search_finds_matching_text(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint("Use frozen dataclasses"))
    await store.add(_make_imprint("Prefer composition over inheritance"))
    results = await store.search("dataclass")
    assert len(results) >= 1
    assert any("dataclass" in r.text.lower() for r in results)


async def test_search_filters_by_scope(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint("Use type annotations", scope="python"))
    await store.add(_make_imprint("Use type annotations", scope="typescript"))
    results = await store.search("type annotations", scope="python")
    assert all(r.scope == "python" for r in results)


async def test_update_text(store: InMemoryImprintStore) -> None:
    added = await store.add(_make_imprint("Old text"))
    updated = await store.update(added.id, text="New text")
    assert updated.text == "New text"
    assert updated.id == added.id


async def test_update_scope(store: InMemoryImprintStore) -> None:
    added = await store.add(_make_imprint(scope="python"))
    updated = await store.update(added.id, scope="global")
    assert updated.scope == "global"


async def test_update_tags(store: InMemoryImprintStore) -> None:
    added = await store.add(_make_imprint(tags=["old"]))
    updated = await store.update(added.id, tags=["new", "updated"])
    assert updated.tags == ["new", "updated"]


async def test_update_nonexistent_raises(store: InMemoryImprintStore) -> None:
    with pytest.raises(KeyError):
        await store.update("nonexistent-id", text="text")


async def test_delete_removes_imprint(store: InMemoryImprintStore) -> None:
    added = await store.add(_make_imprint())
    await store.delete(added.id)
    with pytest.raises(KeyError):
        await store.get(added.id)


async def test_delete_nonexistent_raises(store: InMemoryImprintStore) -> None:
    with pytest.raises(KeyError):
        await store.delete("nonexistent-id")


async def test_get_scopes_returns_distinct(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint(scope="python"))
    await store.add(_make_imprint(scope="python"))
    await store.add(_make_imprint(scope="typescript"))
    scopes = await store.get_scopes()
    assert sorted(scopes) == ["python", "typescript"]


async def test_get_tags_returns_distinct(store: InMemoryImprintStore) -> None:
    await store.add(_make_imprint(tags=["typing", "style"]))
    await store.add(_make_imprint(tags=["typing", "testing"]))
    tags = await store.get_tags()
    assert sorted(tags) == ["style", "testing", "typing"]
