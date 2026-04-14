"""Chat endpoint — streaming curation agent responses."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from engram.api.dependencies import get_llm_client, get_store
from engram.api.models import ChatRequest
from engram.curator.agent import CurationAgent
from engram.llm.base import LLMClient
from engram.storage.base import PreferenceStore

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_class=StreamingResponse)
async def chat(
    request: ChatRequest,
    store: PreferenceStore = Depends(get_store),
    llm_client: LLMClient = Depends(get_llm_client),
) -> StreamingResponse:
    agent = CurationAgent(llm=llm_client, store=store)
    history = [{"role": m.role, "content": m.content} for m in request.history]

    async def stream():
        async for chunk in agent.chat(request.message, history=history):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")
