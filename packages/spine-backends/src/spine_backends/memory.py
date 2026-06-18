"""In-memory semantic memory with a dependency-free default embedder.

Embeds text into a fixed-size vector using hashed word + character-trigram
features (deterministic, offline). Good enough for recall in tests and small
deployments; swap ``embed=`` for a real embedding model in production, or use a
pgvector backend for scale.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Callable
from typing import Any

from spine_core.memory import MemoryHit, MemoryRecord
from spine_core.registry import register_memory

_WORD = re.compile(r"\w+")


def _features(text: str) -> list[str]:
    text = text.lower()
    words = _WORD.findall(text)
    trigrams = [text[i : i + 3] for i in range(max(0, len(text) - 2))]
    return words + trigrams


def default_embed(text: str, dim: int = 256) -> list[float]:
    """Hashed bag-of-features embedding, L2-normalized."""
    vec = [0.0] * dim
    for feature in _features(text):
        digest = hashlib.md5(feature.encode()).hexdigest()  # noqa: S324 - non-crypto hashing
        idx = int(digest, 16) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))  # both are L2-normalized


class InMemoryVectorMemory:
    """Process-local vector memory implementing the core ``Memory`` protocol."""

    def __init__(
        self, *, dim: int = 256, embed: Callable[[str], list[float]] | None = None
    ) -> None:
        self.dim = dim
        self._embed = embed or (lambda text: default_embed(text, dim))
        self._records: list[tuple[MemoryRecord, list[float]]] = []

    async def save(
        self,
        content: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=uuid.uuid4().hex,
            content=content,
            session_id=session_id,
            metadata=metadata or {},
        )
        self._records.append((record, self._embed(content)))
        return record

    async def search(
        self, query: str, *, k: int = 5, session_id: str | None = None
    ) -> list[MemoryHit]:
        qv = self._embed(query)
        scored = [
            MemoryHit(record=record, score=_cosine(qv, vec))
            for record, vec in self._records
            if session_id is None or record.session_id == session_id
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:k]

    async def load(self, session_id: str, *, limit: int = 20) -> list[MemoryRecord]:
        records = [r for r, _ in self._records if r.session_id == session_id]
        return records[-limit:]


def register() -> None:
    register_memory("vector", lambda **cfg: InMemoryVectorMemory(**cfg))


register()
