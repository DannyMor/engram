"""Tests for the REST API server."""

import os
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from engram.models import Confidence, Preference, Source

needs_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def mock_memory():
    """Create a mock MemoryStore."""
    store = MagicMock()
    store.get_all.return_value = [
        Preference(
            id="test-1",
            text="Use pytest fixtures",
            scope="python",
            tags=["testing"],
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        )
    ]
    store.search.return_value = [
        Preference(
            id="test-1",
            text="Use pytest fixtures",
            scope="python",
            tags=["testing"],
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        )
    ]
    store.get_scopes.return_value = ["python", "global"]
    store.get_tags.return_value = ["testing", "pytest"]
    return store


@pytest.fixture
def app(mock_memory):
    """Create test app with mocked memory store."""
    from engram.server import create_app
    return create_app(memory_store=mock_memory)


@pytest.fixture
async def client(app):
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_list_preferences(client, mock_memory):
    response = await client.get("/api/preferences")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "Use pytest fixtures"
    mock_memory.get_all.assert_called_once()


async def test_list_preferences_with_scope_filter(client, mock_memory):
    response = await client.get("/api/preferences?scope=python")
    assert response.status_code == 200
    mock_memory.get_all.assert_called_once_with(scope="python", repo=None, tags=None)


async def test_search_preferences(client, mock_memory):
    response = await client.get("/api/preferences?q=testing")
    assert response.status_code == 200
    mock_memory.search.assert_called_once_with("testing", scope=None, repo=None)


async def test_add_preference(client, mock_memory):
    mock_memory.add.return_value = Preference(
        id="new-1",
        text="Use dataclasses",
        scope="python",
        tags=[],
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )
    response = await client.post(
        "/api/preferences",
        json={"text": "Use dataclasses", "scope": "python"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Use dataclasses"


async def test_delete_preference(client, mock_memory):
    response = await client.delete("/api/preferences/test-1")
    assert response.status_code == 204
    mock_memory.delete.assert_called_once_with("test-1")


async def test_update_preference(client, mock_memory):
    mock_memory.update.return_value = Preference(
        id="test-1",
        text="Updated text",
        scope="python",
        tags=["testing"],
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )
    response = await client.put(
        "/api/preferences/test-1",
        json={"text": "Updated text"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Updated text"


async def test_get_scopes(client, mock_memory):
    response = await client.get("/api/scopes")
    assert response.status_code == 200
    assert response.json() == ["python", "global"]


async def test_get_tags(client, mock_memory):
    response = await client.get("/api/tags")
    assert response.status_code == 200
    assert response.json() == ["testing", "pytest"]


async def test_get_preference_by_id(client, mock_memory):
    mock_memory._mem0.get.return_value = {
        "id": "test-1",
        "memory": "Use pytest fixtures",
        "metadata": {
            "scope": "python",
            "tags": ["testing"],
            "source": "manual",
            "confidence": "high",
        },
    }
    mock_memory._to_preference.return_value = Preference(
        id="test-1",
        text="Use pytest fixtures",
        scope="python",
        tags=["testing"],
        source=Source.MANUAL,
        confidence=Confidence.HIGH,
    )
    response = await client.get("/api/preferences/test-1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-1"
    assert data["text"] == "Use pytest fixtures"


async def test_get_config(client):
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
    assert "has_api_key" in data["llm"]
    # Should NOT contain the actual API key
    assert "api_key" not in str(data).lower() or "has_api_key" in str(data)


async def test_inject_preferences(client, mock_memory):
    response = await client.get("/api/inject?scopes=python,global")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    text = response.text
    assert "<!-- engram:start -->" in text
    assert "<!-- engram:end -->" in text
    assert "Use pytest fixtures" in text
