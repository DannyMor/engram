"""API test fixtures — in-memory store, no mocks."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engram.api.app import create_api
from engram.core.models import EngramConfig
from engram.storage.memory import InMemoryImprintStore
from tests.fakes import FakeLLMClient


@pytest.fixture
def store() -> InMemoryImprintStore:
    return InMemoryImprintStore()


@pytest.fixture
def app(store: InMemoryImprintStore) -> FastAPI:
    app = FastAPI()
    app.state.store = store
    app.state.config = EngramConfig()
    app.state.llm_client = FakeLLMClient(responses=[])
    create_api(app)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
