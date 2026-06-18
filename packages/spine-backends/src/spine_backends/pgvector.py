"""pgvector memory backend — semantic recall backed by Postgres + pgvector.

Scales the vector memory beyond one process. ``asyncpg`` is imported lazily;
the ``pgvector`` extension must be installed in the database. Integration is
exercised when ``SPINE_TEST_PG_DSN`` is set.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from spine_backends.embeddings import HashEmbedder
from spine_core.memory import Embedder, MemoryHit, MemoryRecord
from spine_core.registry import register_memory


class PgVectorMemory:
    """``Memory`` over Postgres + pgvector with cosine-distance recall."""

    def __init__(
        self,
        dsn: str,
        *,
        embedder: Embedder | None = None,
        dim: int = 256,
        table: str = "spine_memory",
        pool: Any = None,
    ) -> None:
        self.dsn = dsn
        self.embedder: Embedder = embedder or HashEmbedder(dim)
        self.dim = dim
        self.table = table
        self._pool = pool

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self.dsn)
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    id         TEXT PRIMARY KEY,
                    session_id TEXT,
                    content    TEXT NOT NULL,
                    metadata   JSONB NOT NULL DEFAULT '{{}}',
                    embedding  vector({self.dim}) NOT NULL,
                    ts         TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        return self._pool

    @staticmethod
    def _vec_literal(vec: list[float]) -> str:
        return "[" + ",".join(repr(x) for x in vec) + "]"

    async def save(
        self,
        content: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        pool = await self._ensure_pool()
        record = MemoryRecord(
            id=uuid.uuid4().hex, content=content, session_id=session_id, metadata=metadata or {}
        )
        embedding = self._vec_literal(await self.embedder.embed(content))
        async with pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {self.table} (id, session_id, content, metadata, embedding) "
                f"VALUES ($1, $2, $3, $4::jsonb, $5::vector)",
                record.id,
                session_id,
                content,
                json.dumps(record.metadata),
                embedding,
            )
        return record

    async def search(
        self, query: str, *, k: int = 5, session_id: str | None = None
    ) -> list[MemoryHit]:
        pool = await self._ensure_pool()
        embedding = self._vec_literal(await self.embedder.embed(query))
        where = "WHERE session_id = $2" if session_id is not None else ""
        args: list[Any] = [embedding] + ([session_id] if session_id is not None else [])
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, session_id, content, metadata, "
                f"1 - (embedding <=> $1::vector) AS score "
                f"FROM {self.table} {where} ORDER BY embedding <=> $1::vector LIMIT {int(k)}",
                *args,
            )
        return [
            MemoryHit(
                record=MemoryRecord(
                    id=row["id"],
                    session_id=row["session_id"],
                    content=row["content"],
                    metadata=json.loads(row["metadata"])
                    if isinstance(row["metadata"], str)
                    else row["metadata"],
                ),
                score=float(row["score"]),
            )
            for row in rows
        ]

    async def load(self, session_id: str, *, limit: int = 20) -> list[MemoryRecord]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, session_id, content, metadata FROM {self.table} "
                f"WHERE session_id = $1 ORDER BY ts DESC LIMIT {int(limit)}",
                session_id,
            )
        return [
            MemoryRecord(
                id=row["id"],
                session_id=row["session_id"],
                content=row["content"],
                metadata=json.loads(row["metadata"])
                if isinstance(row["metadata"], str)
                else row["metadata"],
            )
            for row in rows
        ]


def register() -> None:
    register_memory("pgvector", lambda dsn="", **cfg: PgVectorMemory(dsn, **cfg))


register()
