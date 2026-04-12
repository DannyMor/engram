"""FastAPI REST API server for engram."""

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from engram.config import load_config, resolve_api_key, save_config
from engram.injector import format_injection_block
from engram.logging import setup_logging
from engram.memory import MemoryStore
from engram.models import (
    ConfigResponse,
    EmbedderConfigResponse,
    EngramConfig,
    HealthResponse,
    LLMConfigResponse,
    Preference,
    PreferenceCreate,
    PreferenceUpdate,
    StorageConfigResponse,
)

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

    # --- MCP ---
    from engram.mcp import create_mcp

    mcp = create_mcp(app.state.memory)
    mcp_app = mcp.http_app()
    app.mount("/mcp", mcp_app)
    logger.info("MCP server mounted at /mcp")

    # --- Health ---

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version="0.1.0")

    # --- Preferences CRUD ---

    @app.get("/api/preferences", response_model=list[Preference])
    async def list_preferences(
        q: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: str | None = None,
    ) -> list[Preference]:
        memory: MemoryStore = app.state.memory
        if q is not None:
            return memory.search(q, scope=scope, repo=repo)
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        return memory.get_all(scope=scope, repo=repo, tags=tag_list)

    @app.post("/api/preferences", status_code=201, response_model=Preference)
    async def add_preference(body: PreferenceCreate) -> Preference:
        memory: MemoryStore = app.state.memory
        return memory.add(body)

    @app.get("/api/preferences/{preference_id}", response_model=Preference)
    async def get_preference(preference_id: str) -> Preference:
        memory: MemoryStore = app.state.memory
        mem: dict = memory._mem0.get(preference_id) or {}
        return memory._to_preference(mem)

    @app.put("/api/preferences/{preference_id}", response_model=Preference)
    async def update_preference(preference_id: str, body: PreferenceUpdate) -> Preference:
        memory: MemoryStore = app.state.memory
        return memory.update(
            preference_id,
            text=body.text,
            scope=body.scope,
            repo=body.repo,
            tags=body.tags,
        )

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

        return format_injection_block(all_prefs)

    # --- Config ---

    @app.get("/api/config", response_model=ConfigResponse)
    async def get_config() -> ConfigResponse:
        cfg: EngramConfig = app.state.config
        has_key = resolve_api_key(cfg.llm.api_key_env) is not None
        return ConfigResponse(
            llm=LLMConfigResponse(
                provider=cfg.llm.provider,
                model=cfg.llm.model,
                has_api_key=has_key,
            ),
            embedder=EmbedderConfigResponse(
                provider=cfg.embedder.provider,
                model=cfg.embedder.model,
            ),
            storage=StorageConfigResponse(path=cfg.storage.path),
        )

    @app.put("/api/config", response_model=ConfigResponse)
    async def update_config(body: EngramConfig) -> ConfigResponse:
        save_config(body)
        app.state.config = body
        has_key = resolve_api_key(body.llm.api_key_env) is not None
        return ConfigResponse(
            llm=LLMConfigResponse(
                provider=body.llm.provider,
                model=body.llm.model,
                has_api_key=has_key,
            ),
            embedder=EmbedderConfigResponse(
                provider=body.embedder.provider,
                model=body.embedder.model,
            ),
            storage=StorageConfigResponse(path=body.storage.path),
        )

    # --- Chat (Curation Agent) ---

    from fastapi.responses import StreamingResponse

    from engram.curator import CurationAgent
    from engram.models import ChatRequest

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """Stream a curation agent response."""
        try:
            agent = CurationAgent(app.state.config, app.state.memory)
        except ValueError as e:
            return Response(content=str(e), status_code=503)

        async def stream():
            async for chunk in agent.chat(request.message, request.history):
                yield chunk

        return StreamingResponse(stream(), media_type="text/plain")

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
