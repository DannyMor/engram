"""FastAPI dependency injection — provides store, config, LLM client."""

from fastapi import Request

from engram.core.models import EngramConfig
from engram.llm.base import LLMClient
from engram.storage.base import ImprintStore


async def get_store(request: Request) -> ImprintStore:
    return request.app.state.store


async def get_config(request: Request) -> EngramConfig:
    return request.app.state.config


async def get_llm_client(request: Request) -> LLMClient | None:
    return request.app.state.llm_client
