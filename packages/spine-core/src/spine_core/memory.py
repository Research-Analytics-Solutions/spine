"""Memory protocol — long-term semantic recall across sessions.

Distinct from a checkpoint store (durable serialization of one run's State):
memory is conversational/semantic recall a middleware can search and inject.
Backends (vector stores, pgvector, …) implement this 3-method protocol.
"""

from __future__ import annotations

import time
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    id: str
    content: str
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=time.time)


class MemoryHit(BaseModel):
    record: MemoryRecord
    score: float  # similarity, higher is closer


@runtime_checkable
class Memory(Protocol):
    """Persist and semantically recall snippets across sessions."""

    async def save(
        self, content: str, *, session_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> MemoryRecord: ...

    async def search(
        self, query: str, *, k: int = 5, session_id: str | None = None
    ) -> list[MemoryHit]: ...

    async def load(self, session_id: str, *, limit: int = 20) -> list[MemoryRecord]: ...
