"""Scopes and tags endpoints."""

from fastapi import APIRouter, Depends

from engram.api.dependencies import get_store
from engram.storage.base import ImprintStore

router = APIRouter(tags=["metadata"])


@router.get("/api/scopes", response_model=list[str])
async def get_scopes(store: ImprintStore = Depends(get_store)) -> list[str]:
    return await store.get_scopes()


@router.get("/api/tags", response_model=list[str])
async def get_tags(store: ImprintStore = Depends(get_store)) -> list[str]:
    return await store.get_tags()
