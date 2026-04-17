"""Chat endpoint tests."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engram.api.app import create_api
from engram.core.models import EngramConfig
from engram.llm.base import StopEvent, TextDelta
from engram.storage.memory import InMemoryImprintStore
from tests.fakes import FakeLLMClient


async def test_chat_streams_response() -> None:
    store = InMemoryImprintStore()
    fake_llm = FakeLLMClient(
        responses=[
            [TextDelta(text="Hello!"), StopEvent(reason="end_turn")],
        ]
    )
    app = FastAPI()
    app.state.store = store
    app.state.config = EngramConfig()
    app.state.llm_client = fake_llm
    create_api(app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json={"message": "Hi"})
    assert response.status_code == 200
    assert response.text == "Hello!"
