"""Memory layer — Mem0 wrapper with preference schema and scoping."""

import logging
from pathlib import Path

from mem0 import Memory

from engram.models import (
    Confidence,
    EngramConfig,
    Preference,
    PreferenceCreate,
)

logger = logging.getLogger(__name__)


class MemoryStore:
    """Wraps Mem0 to provide preference-specific storage with scoping."""

    USER_ID = "engram_user"

    def __init__(self, config: EngramConfig) -> None:
        storage_path = Path(config.storage.path).expanduser()
        storage_path.mkdir(parents=True, exist_ok=True)

        mem0_config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "engram_preferences",
                    "path": str(storage_path),
                },
            },
            "embedder": {
                "provider": config.embedder.provider,
                "config": {
                    "model": config.embedder.model,
                },
            },
            "llm": {
                "provider": config.llm.provider,
                "config": {
                    "model": config.llm.model,
                },
            },
        }

        self._mem0 = Memory.from_config(mem0_config)
        self._has_llm = True
        logger.info("MemoryStore initialized with storage at %s", storage_path)

    def add(self, pref: PreferenceCreate) -> Preference:
        """Add a preference. Mem0 handles dedup via LLM."""
        metadata = {
            "scope": pref.scope,
            "repo": pref.repo,
            "tags": pref.tags,
            "source": pref.source.value,
            "confidence": Confidence.HIGH.value,
        }

        kwargs: dict = {
            "user_id": self.USER_ID,
            "metadata": metadata,
        }

        if not self._has_llm:
            kwargs["infer"] = False

        result = self._mem0.add(pref.text, **kwargs)
        logger.info(
            "Added preference (scope=%s, repo=%s): %s",
            pref.scope,
            pref.repo,
            pref.text[:80],
        )

        memory_id = self._extract_id(result)
        return self._get_by_id(memory_id, pref)

    def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Preference]:
        """Semantic search for preferences."""
        filters = self._build_filters(scope=scope, repo=repo)
        kwargs: dict = {"user_id": self.USER_ID}
        if filters:
            kwargs["filters"] = filters

        results = self._mem0.search(query, **kwargs)
        prefs = [self._to_preference(m) for m in results.get("results", results)]
        logger.info(
            "Search query=%s scope=%s repo=%s returned %d results", query, scope, repo, len(prefs)
        )
        return prefs

    def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Preference]:
        """List all preferences, optionally filtered."""
        all_memories = self._mem0.get_all(user_id=self.USER_ID)
        memories = all_memories.get("results", all_memories)

        prefs = [self._to_preference(m) for m in memories]

        if scope:
            prefs = [p for p in prefs if p.scope == scope]
        if repo is not None:
            prefs = [p for p in prefs if p.repo == repo or p.repo is None]
        if tags:
            prefs = [p for p in prefs if any(t in p.tags for t in tags)]

        return prefs

    def delete(self, preference_id: str) -> None:
        """Hard delete a preference."""
        self._mem0.delete(preference_id)
        logger.info("Deleted preference %s", preference_id)

    def update(
        self,
        preference_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Preference:
        """Update an existing preference."""
        existing: dict = self._mem0.get(preference_id) or {}

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
            update_kwargs: dict = {"data": text or existing.get("memory", "")}
            if metadata_changed:
                update_kwargs["metadata"] = current_metadata
            self._mem0.update(preference_id, **update_kwargs)

        updated: dict = self._mem0.get(preference_id) or {}
        logger.info("Updated preference %s", preference_id)
        return self._to_preference(updated)

    def get_scopes(self) -> list[str]:
        """Return all distinct scopes in use."""
        all_prefs = self.get_all()
        return sorted({p.scope for p in all_prefs})

    def get_tags(self) -> list[str]:
        """Return all distinct tags in use."""
        all_prefs = self.get_all()
        tags: set[str] = set()
        for p in all_prefs:
            tags.update(p.tags)
        return sorted(tags)

    def _extract_id(self, result: dict | list) -> str:
        """Extract memory ID from Mem0 add() result."""
        if isinstance(result, dict):
            results = result.get("results", [])
            if results:
                return results[0].get("id", results[0].get("memory_id", ""))
        if isinstance(result, list) and result:
            return result[0].get("id", result[0].get("memory_id", ""))
        return ""

    def _get_by_id(self, memory_id: str, fallback: PreferenceCreate) -> Preference:
        """Fetch a memory by ID and convert to Preference."""
        if memory_id:
            try:
                mem: dict = self._mem0.get(memory_id) or {}
                return self._to_preference(mem)
            except Exception:
                logger.warning("Could not fetch memory %s, using fallback", memory_id)

        return Preference(
            id=memory_id or "unknown",
            text=fallback.text,
            scope=fallback.scope,
            repo=fallback.repo,
            tags=fallback.tags,
            source=fallback.source,
        )

    def _to_preference(self, memory: dict) -> Preference:
        """Convert a Mem0 memory dict to a Preference model."""
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

    def _build_filters(
        self, scope: str | None = None, repo: str | None = None
    ) -> dict | None:
        """Build Mem0-compatible filter dict."""
        conditions = []
        if scope:
            conditions.append({"scope": scope})
        if repo is not None:
            conditions.append({"OR": [{"repo": repo}, {"repo": None}]})
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"AND": conditions}
