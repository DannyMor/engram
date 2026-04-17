"""Imprint CRUD endpoint tests."""

from engram.core.models import Imprint, ImprintCreate


async def test_add_imprint(client, store) -> None:
    response = await client.post(
        "/api/imprints",
        json={
            "text": "Use type annotations",
            "scope": "python",
            "tags": ["typing"],
        },
    )
    assert response.status_code == 201
    imprint = Imprint.model_validate(response.json())
    assert imprint.text == "Use type annotations"
    assert imprint.scope == "python"
    assert imprint.tags == ["typing"]


async def test_list_imprints(client, store) -> None:
    await store.add(ImprintCreate(text="Imprint A", scope="python"))
    response = await client.get("/api/imprints")
    assert response.status_code == 200
    imprints = response.json()
    assert len(imprints) == 1


async def test_list_imprints_with_scope_filter(client, store) -> None:
    await store.add(ImprintCreate(text="Imprint A", scope="python"))
    await store.add(ImprintCreate(text="Imprint B", scope="typescript"))
    response = await client.get("/api/imprints?scope=python")
    assert response.status_code == 200
    imprints = response.json()
    assert len(imprints) == 1
    assert imprints[0]["scope"] == "python"


async def test_get_imprint_by_id(client, store) -> None:
    added = await store.add(ImprintCreate(text="Test imprint", scope="python"))
    response = await client.get(f"/api/imprints/{added.id}")
    assert response.status_code == 200
    imprint = Imprint.model_validate(response.json())
    assert imprint.id == added.id


async def test_get_imprint_not_found(client) -> None:
    response = await client.get("/api/imprints/nonexistent")
    assert response.status_code == 404


async def test_update_imprint(client, store) -> None:
    added = await store.add(ImprintCreate(text="Old text", scope="python"))
    response = await client.put(f"/api/imprints/{added.id}", json={"text": "New text"})
    assert response.status_code == 200
    imprint = Imprint.model_validate(response.json())
    assert imprint.text == "New text"


async def test_delete_imprint(client, store) -> None:
    added = await store.add(ImprintCreate(text="To delete", scope="python"))
    response = await client.delete(f"/api/imprints/{added.id}")
    assert response.status_code == 204
    # Verify it's gone
    response = await client.get(f"/api/imprints/{added.id}")
    assert response.status_code == 404


async def test_search_imprints(client, store) -> None:
    await store.add(ImprintCreate(text="Use frozen dataclasses", scope="python"))
    await store.add(ImprintCreate(text="Prefer composition", scope="python"))
    response = await client.get("/api/imprints?q=dataclass")
    assert response.status_code == 200
    imprints = response.json()
    assert len(imprints) >= 1
