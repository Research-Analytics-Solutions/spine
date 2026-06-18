"""In-process memory backends — semantic vector recall and simple recency buffer.

Both implement the core ``Memory`` protocol. ``InMemoryVectorMemory`` takes any
``Embedder`` (default :class:`HashEmbedder`), so users choose how text is
embedded. ``BufferMemory`` is non-semantic recency recall for the simple case.
"""

from __future__ import annotations

import uuid
from typing import Any

from spine_backends.embeddings import HashEmbedder
from spine_core.memory import Embedder, MemoryHit, MemoryRecord
from spine_core.registry import register_memory


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))  # inputs are L2-normalized


class InMemoryVectorMemory:
    """Process-local vector memory; recall by embedding cosine similarity."""

    def __init__(self, *, embedder: Embedder | None = None, dim: int = 256) -> None:
        self.embedder: Embedder = embedder or HashEmbedder(dim)
        self.dim = dim
        self._records: list[tuple[MemoryRecord, list[float]]] = []

    async def save(
        self,
        content: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=uuid.uuid4().hex, content=content, session_id=session_id, metadata=metadata or {}
        )
        self._records.append((record, await self.embedder.embed(content)))
        return record

    async def search(
        self, query: str, *, k: int = 5, session_id: str | None = None
    ) -> list[MemoryHit]:
        qv = await self.embedder.embed(query)
        hits = [
            MemoryHit(record=record, score=_cosine(qv, vec))
            for record, vec in self._records
            if session_id is None or record.session_id == session_id
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    async def load(self, session_id: str, *, limit: int = 20) -> list[MemoryRecord]:
        records = [r for r, _ in self._records if r.session_id == session_id]
        return records[-limit:]


class BufferMemory:
    """Non-semantic recency memory: ``search`` returns the most recent records.

    Cheap and predictable when similarity is not needed (e.g. a rolling notes
    buffer). ``search`` ignores the query text.
    """

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    async def save(
        self,
        content: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=uuid.uuid4().hex, content=content, session_id=session_id, metadata=metadata or {}
        )
        self._records.append(record)
        return record

    async def search(
        self, query: str, *, k: int = 5, session_id: str | None = None
    ) -> list[MemoryHit]:
        pool = [r for r in self._records if session_id is None or r.session_id == session_id]
        return [MemoryHit(record=r, score=1.0) for r in reversed(pool[-k:])]

    async def load(self, session_id: str, *, limit: int = 20) -> list[MemoryRecord]:
        records = [r for r in self._records if r.session_id == session_id]
        return records[-limit:]


def register() -> None:
    register_memory("vector", lambda **cfg: InMemoryVectorMemory(**cfg))
    register_memory("buffer", lambda **_: BufferMemory())


register()
