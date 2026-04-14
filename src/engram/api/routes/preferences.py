"""Preference CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response

from engram.api.dependencies import get_store
from engram.core.models import Preference, PreferenceCreate, PreferenceUpdate
from engram.storage.base import PreferenceStore

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=list[Preference])
async def list_preferences(
    store: PreferenceStore = Depends(get_store),
    q: str | None = None,
    scope: str | None = None,
    repo: str | None = None,
    tags: str | None = None,
) -> list[Preference]:
    if q is not None:
        return await store.search(q, scope=scope, repo=repo)
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return await store.get_all(scope=scope, repo=repo, tags=tag_list)


@router.post("", status_code=201, response_model=Preference)
async def add_preference(
    body: PreferenceCreate,
    store: PreferenceStore = Depends(get_store),
) -> Preference:
    return await store.add(body)


@router.get("/{preference_id}", response_model=Preference)
async def get_preference(
    preference_id: str,
    store: PreferenceStore = Depends(get_store),
) -> Preference:
    try:
        return await store.get(preference_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Preference not found: {preference_id}")


@router.put("/{preference_id}", response_model=Preference)
async def update_preference(
    preference_id: str,
    body: PreferenceUpdate,
    store: PreferenceStore = Depends(get_store),
) -> Preference:
    try:
        return await store.update(
            preference_id, text=body.text, scope=body.scope, repo=body.repo, tags=body.tags
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Preference not found: {preference_id}")


@router.delete("/{preference_id}", status_code=204)
async def delete_preference(
    preference_id: str,
    store: PreferenceStore = Depends(get_store),
) -> Response:
    try:
        await store.delete(preference_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Preference not found: {preference_id}")
    return Response(status_code=204)
