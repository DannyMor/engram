"""Imprint CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response

from engram.api.dependencies import get_store
from engram.core.models import Imprint, ImprintCreate, ImprintUpdate
from engram.storage.base import ImprintStore

router = APIRouter(prefix="/api/imprints", tags=["imprints"])


@router.get("", response_model=list[Imprint])
async def list_imprints(
    store: ImprintStore = Depends(get_store),
    q: str | None = None,
    scope: str | None = None,
    repo: str | None = None,
    tags: str | None = None,
) -> list[Imprint]:
    if q is not None:
        return await store.search(q, scope=scope, repo=repo)
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return await store.get_all(scope=scope, repo=repo, tags=tag_list)


@router.post("", status_code=201, response_model=Imprint)
async def add_imprint(
    body: ImprintCreate,
    store: ImprintStore = Depends(get_store),
) -> Imprint:
    return await store.add(body)


@router.get("/{imprint_id}", response_model=Imprint)
async def get_imprint(
    imprint_id: str,
    store: ImprintStore = Depends(get_store),
) -> Imprint:
    try:
        return await store.get(imprint_id)
    except KeyError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Imprint not found: {imprint_id}",
        ) from err


@router.put("/{imprint_id}", response_model=Imprint)
async def update_imprint(
    imprint_id: str,
    body: ImprintUpdate,
    store: ImprintStore = Depends(get_store),
) -> Imprint:
    try:
        return await store.update(
            imprint_id, text=body.text, scope=body.scope, repo=body.repo, tags=body.tags
        )
    except KeyError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Imprint not found: {imprint_id}",
        ) from err


@router.delete("/{imprint_id}", status_code=204)
async def delete_imprint(
    imprint_id: str,
    store: ImprintStore = Depends(get_store),
) -> Response:
    try:
        await store.delete(imprint_id)
    except KeyError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Imprint not found: {imprint_id}",
        ) from err
    return Response(status_code=204)
