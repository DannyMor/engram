"""FastAPI application factory — mounts all routers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from engram.api.routes import chat, config, health, imprints, injection, scopes


def create_api(app: FastAPI) -> None:
    """Mount all API routers onto the FastAPI app."""
    app.include_router(health.router)
    app.include_router(imprints.router)
    app.include_router(scopes.router)
    app.include_router(injection.router)
    app.include_router(config.router)
    app.include_router(chat.router)

    @app.get("/", response_class=HTMLResponse)
    async def serve_ui() -> str:
        ui_path = Path(__file__).parent.parent / "ui" / "index.html"
        if ui_path.exists():
            return ui_path.read_text()
        return "<html><body><h1>engram</h1><p>UI not built yet.</p></body></html>"
