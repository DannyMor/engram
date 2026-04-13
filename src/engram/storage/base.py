"""PreferenceStore protocol — async interface for preference persistence."""

from typing import Protocol

from engram.core.models import Preference, PreferenceCreate


class PreferenceStore(Protocol):
    """Async interface for preference storage.

    Implementations:
    - Mem0PreferenceStore (production, wraps Mem0+Qdrant)
    - InMemoryPreferenceStore (testing, dict-backed)
    """

    async def add(self, pref: PreferenceCreate) -> Preference: ...

    async def get(self, preference_id: str) -> Preference: ...

    async def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Preference]: ...

    async def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Preference]: ...

    async def update(
        self,
        preference_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Preference: ...

    async def delete(self, preference_id: str) -> None: ...

    async def get_scopes(self) -> list[str]: ...

    async def get_tags(self) -> list[str]: ...
