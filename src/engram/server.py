"""FastAPI REST API server for engram."""

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from engram.config import load_config, resolve_api_key, save_config
from engram.logging import setup_logging
from engram.memory import MemoryStore
from engram.models import EngramConfig, Preference, PreferenceCreate, PreferenceUpdate

logger = logging.getLogger(__name__)


def create_app(
    config: EngramConfig | None = None,
    memory_store: MemoryStore | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = load_config()
        setup_logging(config.logging.level)

    app = FastAPI(title="engram", version="0.1.0")
    app.state.config = config

    if memory_store is not None:
        app.state.memory = memory_store
    else:
        app.state.memory = MemoryStore(config)

    # --- Health ---

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    # --- Preferences CRUD ---

    @app.get("/api/preferences")
    async def list_preferences(
        q: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: str | None = None,
    ) -> list[dict]:
        memory: MemoryStore = app.state.memory
        if q is not None:
            prefs = memory.search(q, scope=scope, repo=repo)
        else:
            tag_list = [t.strip() for t in tags.split(",")] if tags else None
            prefs = memory.get_all(scope=scope, repo=repo, tags=tag_list)
        return [p.model_dump(mode="json") for p in prefs]

    @app.post("/api/preferences", status_code=201)
    async def add_preference(body: PreferenceCreate) -> dict:
        memory: MemoryStore = app.state.memory
        pref = memory.add(body)
        return pref.model_dump(mode="json")

    @app.get("/api/preferences/{preference_id}")
    async def get_preference(preference_id: str) -> dict:
        memory: MemoryStore = app.state.memory
        mem: dict = memory._mem0.get(preference_id) or {}
        pref = memory._to_preference(mem)
        return pref.model_dump(mode="json")

    @app.put("/api/preferences/{preference_id}")
    async def update_preference(preference_id: str, body: PreferenceUpdate) -> dict:
        memory: MemoryStore = app.state.memory
        pref = memory.update(
            preference_id,
            text=body.text,
            scope=body.scope,
            repo=body.repo,
            tags=body.tags,
        )
        return pref.model_dump(mode="json")

    @app.delete("/api/preferences/{preference_id}", status_code=204)
    async def delete_preference(preference_id: str) -> Response:
        memory: MemoryStore = app.state.memory
        memory.delete(preference_id)
        return Response(status_code=204)

    # --- Scopes & Tags ---

    @app.get("/api/scopes")
    async def get_scopes() -> list[str]:
        memory: MemoryStore = app.state.memory
        return memory.get_scopes()

    @app.get("/api/tags")
    async def get_tags() -> list[str]:
        memory: MemoryStore = app.state.memory
        return memory.get_tags()

    # --- Injection ---

    @app.get("/api/inject", response_class=PlainTextResponse)
    async def inject_preferences(
        scopes: str = Query(default="global"),
        repo: str | None = None,
    ) -> str:
        memory: MemoryStore = app.state.memory
        scope_list = [s.strip() for s in scopes.split(",")]

        seen_ids: set[str] = set()
        all_prefs: list[Preference] = []

        for scope in scope_list:
            prefs = memory.get_all(scope=scope, repo=repo)
            for p in prefs:
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    all_prefs.append(p)

        if not all_prefs:
            return ""

        lines = ["<!-- engram:start -->"]
        for p in all_prefs:
            lines.append(f"- [{p.scope}] {p.text}")
        lines.append("<!-- engram:end -->")

        return "\n".join(lines)

    # --- Config ---

    @app.get("/api/config")
    async def get_config() -> dict:
        cfg: EngramConfig = app.state.config
        has_key = resolve_api_key(cfg.llm.api_key_env) is not None
        return {
            "llm": {
                "provider": cfg.llm.provider,
                "model": cfg.llm.model,
                "has_api_key": has_key,
            },
            "embedder": {
                "provider": cfg.embedder.provider,
                "model": cfg.embedder.model,
            },
            "storage": {"path": cfg.storage.path},
        }

    @app.put("/api/config")
    async def update_config(body: EngramConfig) -> dict:
        save_config(body)
        app.state.config = body
        data = body.model_dump(mode="json")
        api_key = resolve_api_key(body.llm.api_key_env)
        data["has_api_key"] = api_key is not None
        return data

    # --- Static UI ---

    @app.get("/", response_class=HTMLResponse)
    async def serve_ui() -> str:
        ui_path = Path(__file__).parent / "ui" / "index.html"
        if ui_path.exists():
            return ui_path.read_text()
        return "<html><body><h1>engram</h1><p>UI not built yet.</p></body></html>"

    return app


def main() -> None:
    """Entry point for running the server."""
    config = load_config()
    setup_logging(config.logging.level)
    app = create_app(config=config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)
