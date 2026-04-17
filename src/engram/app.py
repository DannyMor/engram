"""Application factory — wires all domains together."""

import logging

from fastapi import FastAPI

from engram.api import create_api
from engram.core.config import load_config, resolve_api_key
from engram.core.logging import setup_logging
from engram.core.models import AnthropicLLMConfig, BedrockLLMConfig, EngramConfig
from engram.llm.anthropic import AnthropicLLMClient
from engram.llm.bedrock import BedrockLLMClient
from engram.mcp import create_mcp
from engram.storage.mem0 import Mem0ImprintStore

logger = logging.getLogger(__name__)


def create_llm_client(config: EngramConfig) -> AnthropicLLMClient | BedrockLLMClient | None:
    """Create the appropriate LLM client based on config."""
    match config.llm:
        case AnthropicLLMConfig() as llm_config:
            if resolve_api_key(llm_config.api_key_env):
                return AnthropicLLMClient(llm_config)
            logger.warning(f"API key not found for {llm_config.api_key_env}, chat disabled")
            return None
        case BedrockLLMConfig() as llm_config:
            return BedrockLLMClient(llm_config)


def create_app(
    config: EngramConfig | None = None,
    store: Mem0ImprintStore | None = None,
) -> FastAPI:
    """Create and configure the full engram application."""
    if config is None:
        config = load_config()
        setup_logging(config.logging.level)

    if store is None:
        store = Mem0ImprintStore(config)

    # MCP (must init before FastAPI for lifespan)
    mcp = create_mcp(store)
    mcp_app = mcp.http_app(path="/")

    app = FastAPI(title="engram", version="0.1.0", lifespan=mcp_app.lifespan)
    app.state.config = config
    app.state.store = store
    app.state.llm_client = create_llm_client(config)

    # Mount MCP and API routes
    app.mount("/mcp", mcp_app)
    create_api(app)

    logger.info("engram application created")
    return app
