"""Pydantic models for preferences, configuration, and API contracts."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Source(StrEnum):
    CODING_SESSION = "coding-session"
    CURATION_AGENT = "curation-agent"
    MANUAL = "manual"


class Confidence(StrEnum):
    HIGH = "high"
    LOW = "low"


class Preference(BaseModel):
    id: str
    text: str
    scope: str
    repo: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: Source = Source.MANUAL
    confidence: Confidence = Confidence.HIGH
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PreferenceCreate(BaseModel):
    text: str
    scope: str
    repo: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: Source = Source.MANUAL


class PreferenceUpdate(BaseModel):
    text: str | None = None
    scope: str | None = None
    repo: str | None = None
    tags: list[str] | None = None


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"


class EmbedderConfig(BaseModel):
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"


class StorageConfig(BaseModel):
    path: str = "~/.engram/data"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 3000


class LoggingConfig(BaseModel):
    level: str = "INFO"


class EngramConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
