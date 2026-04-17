"""Imprint injection endpoint."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from engram.api.dependencies import get_store
from engram.core.models import Imprint
from engram.injection import format_injection_block
from engram.storage.base import ImprintStore

router = APIRouter(tags=["injection"])


@router.get("/api/inject", response_class=PlainTextResponse)
async def inject_imprints(
    store: ImprintStore = Depends(get_store),
    scopes: str = Query(default="global"),
    repo: str | None = None,
) -> str:
    scope_list = [s.strip() for s in scopes.split(",")]
    seen_ids: set[str] = set()
    all_imprints: list[Imprint] = []
    for scope in scope_list:
        imprints = await store.get_all(scope=scope, repo=repo)
        for i in imprints:
            if i.id not in seen_ids:
                seen_ids.add(i.id)
                all_imprints.append(i)
    return format_injection_block(all_imprints)
