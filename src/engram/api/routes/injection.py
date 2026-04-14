"""Preference injection endpoint."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from engram.api.dependencies import get_store
from engram.core.models import Preference
from engram.injection import format_injection_block
from engram.storage.base import PreferenceStore

router = APIRouter(tags=["injection"])


@router.get("/api/inject", response_class=PlainTextResponse)
async def inject_preferences(
    store: PreferenceStore = Depends(get_store),
    scopes: str = Query(default="global"),
    repo: str | None = None,
) -> str:
    scope_list = [s.strip() for s in scopes.split(",")]
    seen_ids: set[str] = set()
    all_prefs: list[Preference] = []
    for scope in scope_list:
        prefs = await store.get_all(scope=scope, repo=repo)
        for p in prefs:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                all_prefs.append(p)
    return format_injection_block(all_prefs)
