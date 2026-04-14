"""Preference CRUD endpoint tests."""

from engram.core.models import Preference, PreferenceCreate


async def test_add_preference(client, store) -> None:
    response = await client.post(
        "/api/preferences",
        json={
            "text": "Use type annotations",
            "scope": "python",
            "tags": ["typing"],
        },
    )
    assert response.status_code == 201
    pref = Preference.model_validate(response.json())
    assert pref.text == "Use type annotations"
    assert pref.scope == "python"
    assert pref.tags == ["typing"]


async def test_list_preferences(client, store) -> None:
    await store.add(PreferenceCreate(text="Pref A", scope="python"))
    response = await client.get("/api/preferences")
    assert response.status_code == 200
    prefs = response.json()
    assert len(prefs) == 1


async def test_list_preferences_with_scope_filter(client, store) -> None:
    await store.add(PreferenceCreate(text="Pref A", scope="python"))
    await store.add(PreferenceCreate(text="Pref B", scope="typescript"))
    response = await client.get("/api/preferences?scope=python")
    assert response.status_code == 200
    prefs = response.json()
    assert len(prefs) == 1
    assert prefs[0]["scope"] == "python"


async def test_get_preference_by_id(client, store) -> None:
    added = await store.add(PreferenceCreate(text="Test pref", scope="python"))
    response = await client.get(f"/api/preferences/{added.id}")
    assert response.status_code == 200
    pref = Preference.model_validate(response.json())
    assert pref.id == added.id


async def test_get_preference_not_found(client) -> None:
    response = await client.get("/api/preferences/nonexistent")
    assert response.status_code == 404


async def test_update_preference(client, store) -> None:
    added = await store.add(PreferenceCreate(text="Old text", scope="python"))
    response = await client.put(f"/api/preferences/{added.id}", json={"text": "New text"})
    assert response.status_code == 200
    pref = Preference.model_validate(response.json())
    assert pref.text == "New text"


async def test_delete_preference(client, store) -> None:
    added = await store.add(PreferenceCreate(text="To delete", scope="python"))
    response = await client.delete(f"/api/preferences/{added.id}")
    assert response.status_code == 204
    # Verify it's gone
    response = await client.get(f"/api/preferences/{added.id}")
    assert response.status_code == 404


async def test_search_preferences(client, store) -> None:
    await store.add(PreferenceCreate(text="Use frozen dataclasses", scope="python"))
    await store.add(PreferenceCreate(text="Prefer composition", scope="python"))
    response = await client.get("/api/preferences?q=dataclass")
    assert response.status_code == 200
    prefs = response.json()
    assert len(prefs) >= 1
