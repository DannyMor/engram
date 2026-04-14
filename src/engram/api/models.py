"""API request/response models — separate from domain models."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class LLMConfigResponse(BaseModel):
    provider: str
    model: str
    has_api_key: bool


class EmbedderConfigResponse(BaseModel):
    provider: str
    model: str


class StorageConfigResponse(BaseModel):
    path: str


class ConfigResponse(BaseModel):
    llm: LLMConfigResponse
    embedder: EmbedderConfigResponse
    storage: StorageConfigResponse


class ConfigUpdateRequest(BaseModel):
    """Restricted config update — only safe fields."""

    llm_model: str | None = None
    embedder_model: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
