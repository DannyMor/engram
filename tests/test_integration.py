"""Integration tests — full stack with real Mem0 (requires credentials)."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from engram.api.models import ConfigResponse, HealthResponse
from engram.app import create_app
from engram.core.models import (
    BedrockLLMConfig,
    EmbedderConfig,
    EngramConfig,
    Imprint,
    LoggingConfig,
    ProfileAuth,
    ServerConfig,
    StorageConfig,
)

needs_credentials = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("AWS_PROFILE"),
    reason="No LLM credentials available",
)


@pytest.fixture
def integration_config(tmp_path):
    return EngramConfig(
        server=ServerConfig(host="127.0.0.1", port=3099),
        storage=StorageConfig(path=str(tmp_path / "data")),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
        llm=BedrockLLMConfig(
            model="us.anthropic.claude-sonnet-4-20250514-v1:0",
            aws_auth=ProfileAuth(
                profile=os.environ.get("AWS_PROFILE", "default"),
                region=os.environ.get("AWS_REGION", "us-east-1"),
            )
            if os.environ.get("AWS_PROFILE")
            else None,
        ),
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


@needs_credentials
async def test_full_imprint_lifecycle(integration_client):
    """Test add -> list -> search -> update -> inject -> delete."""
    client = integration_client

    res = await client.get("/api/health")
    assert res.status_code == 200
    health = HealthResponse.model_validate(res.json())
    assert health.status == "ok"

    res = await client.post(
        "/api/imprints",
        json={
            "text": "Always use type annotations in function signatures",
            "scope": "python",
            "tags": ["typing"],
        },
    )
    assert res.status_code == 201
    imprint = Imprint.model_validate(res.json())
    assert imprint.scope == "python"
    imprint_id = imprint.id

    res = await client.get("/api/imprints?scope=python")
    assert res.status_code == 200
    imprints = [Imprint.model_validate(i) for i in res.json()]
    assert len(imprints) >= 1

    res = await client.get("/api/imprints?q=type annotations")
    assert res.status_code == 200
    results = [Imprint.model_validate(i) for i in res.json()]
    assert len(results) >= 1

    res = await client.get("/api/inject?scopes=python,global")
    assert res.status_code == 200
    assert "type annotations" in res.text

    res = await client.put(
        f"/api/imprints/{imprint_id}",
        json={
            "text": "Always use type annotations on all public function signatures",
        },
    )
    assert res.status_code == 200
    updated = Imprint.model_validate(res.json())
    assert "public" in updated.text

    res = await client.delete(f"/api/imprints/{imprint_id}")
    assert res.status_code == 204

    res = await client.get("/api/imprints?scope=python")
    ids = [i["id"] for i in res.json()]
    assert imprint_id not in ids


@needs_credentials
async def test_config_roundtrip(integration_client):
    res = await integration_client.get("/api/config")
    assert res.status_code == 200
    config = ConfigResponse.model_validate(res.json())
    assert config.llm.provider == "aws_bedrock"
    assert config.embedder.provider == "fastembed"
