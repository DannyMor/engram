"""In-memory preference store — dict-backed, no external dependencies."""

import uuid
from datetime import UTC, datetime

from engram.core.models import Confidence, Preference, PreferenceCreate


class InMemoryPreferenceStore:
    """Dict-backed PreferenceStore for testing and embedding-free mode."""

    def __init__(self) -> None:
        self._prefs: dict[str, Preference] = {}

    async def add(self, pref: PreferenceCreate) -> Preference:
        preference = Preference(
            id=str(uuid.uuid4()),
            text=pref.text,
            scope=pref.scope,
            repo=pref.repo,
            tags=pref.tags,
            source=pref.source,
            confidence=Confidence.HIGH,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._prefs[preference.id] = preference
        return preference

    async def get(self, preference_id: str) -> Preference:
        try:
            return self._prefs[preference_id]
        except KeyError:
            raise KeyError(f"Preference not found: {preference_id}")

    async def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Preference]:
        query_lower = query.lower()
        results = [p for p in self._prefs.values() if query_lower in p.text.lower()]
        if scope:
            results = [p for p in results if p.scope == scope]
        if repo is not None:
            results = [p for p in results if p.repo == repo or p.repo is None]
        return results

    async def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Preference]:
        results = list(self._prefs.values())
        if scope:
            results = [p for p in results if p.scope == scope]
        if repo is not None:
            results = [p for p in results if p.repo == repo or p.repo is None]
        if tags:
            results = [p for p in results if any(t in p.tags for t in tags)]
        return results

    async def update(
        self,
        preference_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Preference:
        existing = await self.get(preference_id)
        updated = existing.model_copy(
            update={
                k: v
                for k, v in {"text": text, "scope": scope, "repo": repo, "tags": tags}.items()
                if v is not None
            }
            | {"updated_at": datetime.now(UTC)},
        )
        self._prefs[preference_id] = updated
        return updated

    async def delete(self, preference_id: str) -> None:
        if preference_id not in self._prefs:
            raise KeyError(f"Preference not found: {preference_id}")
        del self._prefs[preference_id]

    async def get_scopes(self) -> list[str]:
        return sorted({p.scope for p in self._prefs.values()})

    async def get_tags(self) -> list[str]:
        tags: set[str] = set()
        for p in self._prefs.values():
            tags.update(p.tags)
        return sorted(tags)
