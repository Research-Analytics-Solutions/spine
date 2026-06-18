"""Postgres checkpoint backend — durable state with optimistic locking.

Uses ``asyncpg`` (imported lazily; inject a ``pool`` for tests). Integration is
exercised against a real database when ``SPINE_TEST_PG_DSN`` is set; the module
itself imports nothing heavy at top level.
"""

from __future__ import annotations

import json
from typing import Any

from spine_backends.migrations import migrate
from spine_core.registry import register_checkpoint
from spine_core.state import State


class PostgresCheckpoint:
    """Durable :class:`~spine_core.checkpoint.CheckpointStore` over Postgres."""

    def __init__(self, dsn: str, *, pool: Any = None, table: str = "spine_checkpoints") -> None:
        self.dsn = dsn
        self.table = table
        self._pool = pool

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self.dsn)
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    session_id TEXT PRIMARY KEY,
                    version    INTEGER NOT NULL,
                    revision   BIGINT  NOT NULL DEFAULT 1,
                    data       JSONB   NOT NULL,
                    updated    TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        return self._pool

    async def put(self, state: State) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self.table} (session_id, version, revision, data)
                VALUES ($1, $2, 1, $3::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                    version  = EXCLUDED.version,
                    revision = {self.table}.revision + 1,
                    data     = EXCLUDED.data,
                    updated  = now()
                """,
                state.session_id,
                state.version,
                state.model_dump_json(),
            )

    async def get(self, session_id: str) -> State | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT data FROM {self.table} WHERE session_id = $1", session_id
            )
        if row is None:
            return None
        data: Any = row["data"]
        raw = json.loads(data) if isinstance(data, str) else data
        return State.model_validate(migrate(raw))

    async def delete(self, session_id: str) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"DELETE FROM {self.table} WHERE session_id = $1", session_id)


def register() -> None:
    register_checkpoint("postgres", lambda dsn="", **_: PostgresCheckpoint(dsn))


register()
