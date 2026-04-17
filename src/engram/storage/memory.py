"""In-memory imprint store — dict-backed, no external dependencies."""

import uuid
from datetime import UTC, datetime

from engram.core.models import Confidence, Imprint, ImprintCreate


class InMemoryImprintStore:
    """Dict-backed ImprintStore for testing and embedding-free mode."""

    def __init__(self) -> None:
        self._imprints: dict[str, Imprint] = {}

    async def add(self, imprint: ImprintCreate) -> Imprint:
        created = Imprint(
            id=str(uuid.uuid4()),
            text=imprint.text,
            scope=imprint.scope,
            repo=imprint.repo,
            tags=imprint.tags,
            source=imprint.source,
            confidence=Confidence.HIGH,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._imprints[created.id] = created
        return created

    async def get(self, imprint_id: str) -> Imprint:
        try:
            return self._imprints[imprint_id]
        except KeyError as err:
            raise KeyError(f"Imprint not found: {imprint_id}") from err

    async def search(
        self, query: str, scope: str | None = None, repo: str | None = None
    ) -> list[Imprint]:
        query_lower = query.lower()
        results = [i for i in self._imprints.values() if query_lower in i.text.lower()]
        if scope:
            results = [i for i in results if i.scope == scope]
        if repo is not None:
            results = [i for i in results if i.repo == repo or i.repo is None]
        return results

    async def get_all(
        self,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Imprint]:
        results = list(self._imprints.values())
        if scope:
            results = [i for i in results if i.scope == scope]
        if repo is not None:
            results = [i for i in results if i.repo == repo or i.repo is None]
        if tags:
            results = [i for i in results if any(t in i.tags for t in tags)]
        return results

    async def update(
        self,
        imprint_id: str,
        text: str | None = None,
        scope: str | None = None,
        repo: str | None = None,
        tags: list[str] | None = None,
    ) -> Imprint:
        existing = await self.get(imprint_id)
        updated = existing.model_copy(
            update={
                k: v
                for k, v in {"text": text, "scope": scope, "repo": repo, "tags": tags}.items()
                if v is not None
            }
            | {"updated_at": datetime.now(UTC)},
        )
        self._imprints[imprint_id] = updated
        return updated

    async def delete(self, imprint_id: str) -> None:
        if imprint_id not in self._imprints:
            raise KeyError(f"Imprint not found: {imprint_id}")
        del self._imprints[imprint_id]

    async def get_scopes(self) -> list[str]:
        return sorted({i.scope for i in self._imprints.values()})

    async def get_tags(self) -> list[str]:
        tags: set[str] = set()
        for i in self._imprints.values():
            tags.update(i.tags)
        return sorted(tags)
