"""Integration tests — full stack with real Mem0 (requires API key)."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from engram.models import (
    ConfigResponse,
    EmbedderConfig,
    EngramConfig,
    HealthResponse,
    LLMConfig,
    LoggingConfig,
    Preference,
    ServerConfig,
    StorageConfig,
)
from engram.server import create_app

needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def integration_config(tmp_path):
    return EngramConfig(
        server=ServerConfig(host="127.0.0.1", port=3099),
        storage=StorageConfig(path=str(tmp_path / "data")),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
        llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
        logging=LoggingConfig(level="DEBUG"),
    )


@pytest.fixture
def integration_app(integration_config):
    return create_app(config=integration_config)


@pytest.fixture
async def integration_client(integration_app):
    transport = ASGITransport(app=integration_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@needs_api_key
async def test_full_preference_lifecycle(integration_client):
    """Test add -> list -> search -> update -> inject -> delete."""
    client = integration_client

    # Health check
    res = await client.get("/api/health")
    assert res.status_code == 200
    health = HealthResponse.model_validate(res.json())
    assert health.status == "ok"

    # Add a preference
    res = await client.post("/api/preferences", json={
        "text": "Always use type annotations in function signatures",
        "scope": "python",
        "tags": ["typing"],
    })
    assert res.status_code == 201
    pref = Preference.model_validate(res.json())
    assert pref.scope == "python"
    pref_id = pref.id

    # List preferences
    res = await client.get("/api/preferences?scope=python")
    assert res.status_code == 200
    prefs = [Preference.model_validate(p) for p in res.json()]
    assert len(prefs) >= 1

    # Search
    res = await client.get("/api/preferences?q=type annotations")
    assert res.status_code == 200
    results = [Preference.model_validate(p) for p in res.json()]
    assert len(results) >= 1

    # Inject
    res = await client.get("/api/inject?scopes=python,global")
    assert res.status_code == 200
    assert "type annotations" in res.text
    assert "<!-- engram:start -->" in res.text

    # Update
    res = await client.put(f"/api/preferences/{pref_id}", json={
        "text": "Always use type annotations on all public function signatures",
    })
    assert res.status_code == 200
    updated = Preference.model_validate(res.json())
    assert "public" in updated.text

    # Delete
    res = await client.delete(f"/api/preferences/{pref_id}")
    assert res.status_code == 204

    # Verify deletion
    res = await client.get("/api/preferences?scope=python")
    ids = [p["id"] for p in res.json()]
    assert pref_id not in ids


@needs_api_key
async def test_config_roundtrip(integration_client):
    """Test config read returns valid typed response."""
    res = await integration_client.get("/api/config")
    assert res.status_code == 200
    config = ConfigResponse.model_validate(res.json())
    assert config.llm.provider == "anthropic"
    assert config.embedder.provider == "fastembed"


@needs_api_key
async def test_scopes_and_tags_reflect_data(integration_client):
    """Test that scopes/tags endpoints reflect added preferences."""
    client = integration_client

    # Add preferences in different scopes with tags
    await client.post("/api/preferences", json={
        "text": "Use pytest fixtures",
        "scope": "python",
        "tags": ["testing"],
    })
    await client.post("/api/preferences", json={
        "text": "Prefer const over let",
        "scope": "typescript",
        "tags": ["style"],
    })

    res = await client.get("/api/scopes")
    assert res.status_code == 200
    scopes: list[str] = res.json()
    assert "python" in scopes
    assert "typescript" in scopes

    res = await client.get("/api/tags")
    assert res.status_code == 200
    tags: list[str] = res.json()
    assert "testing" in tags
    assert "style" in tags
