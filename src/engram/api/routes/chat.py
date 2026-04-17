"""Chat endpoint — streaming collector agent responses."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from engram.api.dependencies import get_llm_client, get_store
from engram.api.models import ChatRequest
from engram.collector.agent import ImprintCollector
from engram.llm.base import LLMClient
from engram.storage.base import ImprintStore

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_class=StreamingResponse)
async def chat(
    request: ChatRequest,
    store: ImprintStore = Depends(get_store),
    llm_client: LLMClient | None = Depends(get_llm_client),
) -> StreamingResponse:
    if llm_client is None:
        raise HTTPException(
            status_code=503,
            detail="Chat requires an LLM provider. Set ANTHROPIC_API_KEY or configure"
            " a Bedrock provider in ~/.engram/config.yaml",
        )

    agent = ImprintCollector(llm=llm_client, store=store)
    history = [{"role": m.role, "content": m.content} for m in request.history]

    async def stream():
        async for chunk in agent.chat(request.message, history=history):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")
