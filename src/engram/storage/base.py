"""ImprintStore protocol — async interface for imprint persistence."""

from typing import Protocol

from engram.core.models import Imprint, ImprintCreate


class ImprintStore(Protocol):
    """Async interface for imprint storage.

    Implementations:
    - Mem0ImprintStore (production, wraps Mem0+Qdrant)
    - InMemoryImprintStore (testing, dict-backed)
    """

    async def add(self, imprint: ImprintCreate) -> Imprint: ...

    async def get(self, imprint_id: str) -> Imprint: ...

    async def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Imprint]: ...

    async def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Imprint]: ...

    async def update(
        self,
        imprint_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Imprint: ...

    async def delete(self, imprint_id: str) -> None: ...

    async def get_scopes(self) -> list[str]: ...

    async def get_tags(self) -> list[str]: ...
