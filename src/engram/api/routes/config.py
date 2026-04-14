"""Configuration endpoints."""

from fastapi import APIRouter, Depends

from engram.api.dependencies import get_config
from engram.api.models import (
    ConfigResponse,
    ConfigUpdateRequest,
    EmbedderConfigResponse,
    LLMConfigResponse,
    StorageConfigResponse,
)
from engram.core.config import resolve_api_key, save_config
from engram.core.models import AnthropicLLMConfig, EngramConfig

router = APIRouter(tags=["config"])


@router.get("/api/config", response_model=ConfigResponse)
async def get_config_endpoint(config: EngramConfig = Depends(get_config)) -> ConfigResponse:
    has_key = False
    match config.llm:
        case AnthropicLLMConfig(api_key_env=env):
            has_key = resolve_api_key(env) is not None
        case _:
            has_key = True  # Bedrock uses IAM, not API key

    return ConfigResponse(
        llm=LLMConfigResponse(
            provider=config.llm.provider,
            model=config.llm.model,
            has_api_key=has_key,
        ),
        embedder=EmbedderConfigResponse(
            provider=config.embedder.provider,
            model=config.embedder.model,
        ),
        storage=StorageConfigResponse(path=config.storage.path),
    )
