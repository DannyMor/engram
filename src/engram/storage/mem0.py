"""Mem0-backed imprint store — wraps Mem0+Qdrant with async interface."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from mem0 import Memory

from engram.core.config import resolve_api_key
from engram.core.models import (
    AnthropicLLMConfig,
    BedrockLLMConfig,
    Confidence,
    EngramConfig,
    Imprint,
    ImprintCreate,
    ProfileAuth,
    StaticAuth,
)

logger = logging.getLogger(__name__)

USER_ID = "engram_user"


class Mem0ImprintStore:
    """Production ImprintStore backed by Mem0 + embedded Qdrant."""

    def __init__(self, config: EngramConfig) -> None:
        storage_path = Path(config.storage.path).expanduser()
        storage_path.mkdir(parents=True, exist_ok=True)

        mem0_config: dict[str, Any] = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "engram_preferences",
                    "path": str(storage_path),
                    "embedding_model_dims": 384,
                },
            },
            "embedder": {
                "provider": config.embedder.provider,
                "config": {
                    "model": config.embedder.model,
                    "embedding_dims": 384,
                },
            },
            "llm": {
                "provider": self._llm_provider(config),
                "config": self._llm_config(config),
            },
        }

        self._mem0 = Memory.from_config(mem0_config)
        logger.info(f"Mem0ImprintStore initialized with storage at {storage_path}")

    async def add(self, imprint: ImprintCreate) -> Imprint:
        metadata: dict[str, Any] = {
            "scope": imprint.scope,
            "repo": imprint.repo,
            "tags": imprint.tags,
            "source": imprint.source.value,
            "confidence": Confidence.HIGH.value,
        }
        result = await asyncio.to_thread(
            self._mem0.add, imprint.text, user_id=USER_ID, metadata=metadata
        )
        memory_id = self._extract_id(result)
        logger.info(f"Added imprint (scope={imprint.scope}): {imprint.text[:80]}")
        return await self._get_by_id(memory_id, imprint)

    async def get(self, imprint_id: str) -> Imprint:
        mem: dict[str, Any] | None = await asyncio.to_thread(self._mem0.get, imprint_id)
        if not mem:
            raise KeyError(f"Imprint not found: {imprint_id}")
        return self._to_imprint(mem)

    async def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Imprint]:
        filters = self._build_filters(scope=scope, repo=repo)
        kwargs: dict[str, Any] = {"user_id": USER_ID}
        if filters:
            kwargs["filters"] = filters
        results: dict[str, Any] = await asyncio.to_thread(self._mem0.search, query, **kwargs)
        imprints = [self._to_imprint(m) for m in results.get("results", results)]
        logger.info(f"Search query={query} scope={scope} returned {len(imprints)} results")
        return imprints

    async def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Imprint]:
        all_memories: dict[str, Any] = await asyncio.to_thread(self._mem0.get_all, user_id=USER_ID)
        memories = all_memories.get("results", all_memories)
        imprints = [self._to_imprint(m) for m in memories]
        if scope:
            imprints = [i for i in imprints if i.scope == scope]
        if repo is not None:
            imprints = [i for i in imprints if i.repo == repo or i.repo is None]
        if tags:
            imprints = [i for i in imprints if any(t in i.tags for t in tags)]
        return imprints

    async def update(
        self,
        imprint_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Imprint:
        existing: dict[str, Any] | None = await asyncio.to_thread(self._mem0.get, imprint_id)
        if not existing:
            raise KeyError(f"Imprint not found: {imprint_id}")

        current_metadata = existing.get("metadata", {})
        metadata_changed = False
        if scope is not None:
            current_metadata["scope"] = scope
            metadata_changed = True
        if repo is not None:
            current_metadata["repo"] = repo
            metadata_changed = True
        if tags is not None:
            current_metadata["tags"] = tags
            metadata_changed = True

        if text or metadata_changed:
            update_kwargs: dict[str, Any] = {"data": text or existing.get("memory", "")}
            if metadata_changed:
                update_kwargs["metadata"] = current_metadata
            await asyncio.to_thread(self._mem0.update, imprint_id, **update_kwargs)

        updated: dict[str, Any] | None = await asyncio.to_thread(self._mem0.get, imprint_id)
        logger.info(f"Updated imprint {imprint_id}")
        return self._to_imprint(updated or {})

    async def delete(self, imprint_id: str) -> None:
        await asyncio.to_thread(self._mem0.delete, imprint_id)
        logger.info(f"Deleted imprint {imprint_id}")

    async def get_scopes(self) -> list[str]:
        all_imprints = await self.get_all()
        return sorted({i.scope for i in all_imprints})

    async def get_tags(self) -> list[str]:
        all_imprints = await self.get_all()
        tags: set[str] = set()
        for i in all_imprints:
            tags.update(i.tags)
        return sorted(tags)

    # --- Private helpers ---

    @staticmethod
    def _llm_provider(config: EngramConfig) -> str:
        match config.llm:
            case BedrockLLMConfig():
                return "aws_bedrock"
            case AnthropicLLMConfig():
                return "anthropic"

    @staticmethod
    def _llm_config(config: EngramConfig) -> dict[str, Any]:
        match config.llm:
            case BedrockLLMConfig(model=model, aws_auth=None):
                return {"model": model}
            case BedrockLLMConfig(model=model, aws_auth=ProfileAuth(profile=p, region=r)):
                os.environ["AWS_PROFILE"] = p
                return {"model": model, "aws_region": r} if r else {"model": model}
            case BedrockLLMConfig(
                model=model,
                aws_auth=StaticAuth(
                    access_key_id=k,
                    secret_access_key=s,
                    session_token=t,
                    region=r,
                ),
            ):
                return {
                    "model": model,
                    "aws_access_key_id": k,
                    "aws_secret_access_key": s,
                    "aws_session_token": t,
                    "aws_region": r,
                }
            case AnthropicLLMConfig(model=model, api_key_env=env):
                api_key = resolve_api_key(env)
                return {"model": model, "api_key": api_key} if api_key else {"model": model}

    @staticmethod
    def _extract_id(result: dict[str, Any] | list[dict[str, Any]]) -> str:
        match result:
            case {"results": [first, *_]}:
                return first.get("id", first.get("memory_id", ""))
            case [first, *_]:
                return first.get("id", first.get("memory_id", ""))
            case _:
                return ""

    async def _get_by_id(self, memory_id: str, fallback: ImprintCreate) -> Imprint:
        if memory_id:
            try:
                return await self.get(memory_id)
            except (KeyError, Exception):
                logger.warning(f"Could not fetch memory {memory_id}, using fallback")
        return Imprint(
            id=memory_id or "unknown",
            text=fallback.text,
            scope=fallback.scope,
            repo=fallback.repo,
            tags=fallback.tags,
            source=fallback.source,
        )

    @staticmethod
    def _to_imprint(memory: dict[str, Any]) -> Imprint:
        metadata = memory.get("metadata") or {}
        return Imprint(
            id=memory.get("id", memory.get("memory_id", "")),
            text=memory.get("memory", ""),
            scope=metadata.get("scope", "global"),
            repo=metadata.get("repo"),
            tags=metadata.get("tags", []),
            source=metadata.get("source", "manual"),
            confidence=metadata.get("confidence", "high"),
            created_at=memory.get("created_at"),
            updated_at=memory.get("updated_at"),
        )

    @staticmethod
    def _build_filters(scope: str | None = None, repo: str | None = None) -> dict[str, Any] | None:
        conditions: list[dict[str, Any]] = []
        if scope:
            conditions.append({"scope": scope})
        if repo is not None:
            conditions.append({"OR": [{"repo": repo}, {"repo": None}]})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"AND": conditions}
