"""Mem0-backed preference store — wraps Mem0+Qdrant with async interface."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from mem0 import Memory

from engram.core.config import resolve_api_key
from engram.core.models import (
    AnthropicLLMConfig,
    BedrockLLMConfig,
    Confidence,
    EngramConfig,
    Preference,
    PreferenceCreate,
)

logger = logging.getLogger(__name__)

USER_ID = "engram_user"


class Mem0PreferenceStore:
    """Production PreferenceStore backed by Mem0 + embedded Qdrant."""

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
        logger.info(f"Mem0PreferenceStore initialized with storage at {storage_path}")

    async def add(self, pref: PreferenceCreate) -> Preference:
        metadata: dict[str, Any] = {
            "scope": pref.scope,
            "repo": pref.repo,
            "tags": pref.tags,
            "source": pref.source.value,
            "confidence": Confidence.HIGH.value,
        }
        result = await asyncio.to_thread(
            self._mem0.add, pref.text, user_id=USER_ID, metadata=metadata
        )
        memory_id = self._extract_id(result)
        logger.info(f"Added preference (scope={pref.scope}): {pref.text[:80]}")
        return await self._get_by_id(memory_id, pref)

    async def get(self, preference_id: str) -> Preference:
        mem: dict[str, Any] | None = await asyncio.to_thread(self._mem0.get, preference_id)
        if not mem:
            raise KeyError(f"Preference not found: {preference_id}")
        return self._to_preference(mem)

    async def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Preference]:
        filters = self._build_filters(scope=scope, repo=repo)
        kwargs: dict[str, Any] = {"user_id": USER_ID}
        if filters:
            kwargs["filters"] = filters
        results: dict[str, Any] = await asyncio.to_thread(
            self._mem0.search, query, **kwargs
        )
        prefs = [self._to_preference(m) for m in results.get("results", results)]
        logger.info(f"Search query={query} scope={scope} returned {len(prefs)} results")
        return prefs

    async def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Preference]:
        all_memories: dict[str, Any] = await asyncio.to_thread(
            self._mem0.get_all, user_id=USER_ID
        )
        memories = all_memories.get("results", all_memories)
        prefs = [self._to_preference(m) for m in memories]
        if scope:
            prefs = [p for p in prefs if p.scope == scope]
        if repo is not None:
            prefs = [p for p in prefs if p.repo == repo or p.repo is None]
        if tags:
            prefs = [p for p in prefs if any(t in p.tags for t in tags)]
        return prefs

    async def update(
        self,
        preference_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Preference:
        existing: dict[str, Any] | None = await asyncio.to_thread(
            self._mem0.get, preference_id
        )
        if not existing:
            raise KeyError(f"Preference not found: {preference_id}")

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
            await asyncio.to_thread(self._mem0.update, preference_id, **update_kwargs)

        updated: dict[str, Any] | None = await asyncio.to_thread(
            self._mem0.get, preference_id
        )
        logger.info(f"Updated preference {preference_id}")
        return self._to_preference(updated or {})

    async def delete(self, preference_id: str) -> None:
        await asyncio.to_thread(self._mem0.delete, preference_id)
        logger.info(f"Deleted preference {preference_id}")

    async def get_scopes(self) -> list[str]:
        all_prefs = await self.get_all()
        return sorted({p.scope for p in all_prefs})

    async def get_tags(self) -> list[str]:
        all_prefs = await self.get_all()
        tags: set[str] = set()
        for p in all_prefs:
            tags.update(p.tags)
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
            case BedrockLLMConfig(model=model, aws_region=region):
                return {"model": model, "aws_region": region}
            case AnthropicLLMConfig(model=model, api_key_env=env):
                cfg: dict[str, Any] = {"model": model}
                api_key = resolve_api_key(env)
                if api_key:
                    cfg["api_key"] = api_key
                return cfg

    @staticmethod
    def _extract_id(result: dict[str, Any] | list[dict[str, Any]]) -> str:
        match result:
            case {"results": [first, *_]}:
                return first.get("id", first.get("memory_id", ""))
            case [first, *_]:
                return first.get("id", first.get("memory_id", ""))
            case _:
                return ""

    async def _get_by_id(self, memory_id: str, fallback: PreferenceCreate) -> Preference:
        if memory_id:
            try:
                return await self.get(memory_id)
            except (KeyError, Exception):
                logger.warning(f"Could not fetch memory {memory_id}, using fallback")
        return Preference(
            id=memory_id or "unknown",
            text=fallback.text,
            scope=fallback.scope,
            repo=fallback.repo,
            tags=fallback.tags,
            source=fallback.source,
        )

    @staticmethod
    def _to_preference(memory: dict[str, Any]) -> Preference:
        metadata = memory.get("metadata", {})
        return Preference(
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
    def _build_filters(
        scope: str | None = None, repo: str | None = None
    ) -> dict[str, Any] | None:
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
