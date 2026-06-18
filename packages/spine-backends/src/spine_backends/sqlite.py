"""SQLite checkpoint backend — durable state for crash recovery and resume.

Uses the stdlib ``sqlite3`` driver offloaded to a worker thread (via anyio) so
the async kernel never blocks. WAL mode keeps reads and writes concurrent. A
monotonic ``revision`` column supports optimistic-locking checks.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import anyio

from spine_backends.migrations import migrate
from spine_core.registry import register_checkpoint
from spine_core.state import State

_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    session_id TEXT PRIMARY KEY,
    version    INTEGER NOT NULL,
    revision   INTEGER NOT NULL DEFAULT 1,
    data       TEXT    NOT NULL,
    updated    REAL    NOT NULL
)
"""


class SQLiteCheckpoint:
    """Durable :class:`~spine_core.checkpoint.CheckpointStore` over SQLite."""

    def __init__(self, path: str | Path = "spine.db") -> None:
        self.path = str(path)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    async def put(self, state: State) -> None:
        await anyio.to_thread.run_sync(self._put_sync, state)

    def _put_sync(self, state: State) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (session_id, version, revision, data, updated)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    version  = excluded.version,
                    revision = checkpoints.revision + 1,
                    data     = excluded.data,
                    updated  = excluded.updated
                """,
                (state.session_id, state.version, state.model_dump_json(), time.time()),
            )

    async def get(self, session_id: str) -> State | None:
        return await anyio.to_thread.run_sync(self._get_sync, session_id)

    def _get_sync(self, session_id: str) -> State | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM checkpoints WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        raw = migrate(json.loads(row[0]))
        return State.model_validate(raw)

    async def delete(self, session_id: str) -> None:
        await anyio.to_thread.run_sync(self._delete_sync, session_id)

    def _delete_sync(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM checkpoints WHERE session_id = ?", (session_id,))

    async def revision(self, session_id: str) -> int:
        """Current optimistic-lock revision for a session (0 if absent)."""
        return await anyio.to_thread.run_sync(self._revision_sync, session_id)

    def _revision_sync(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT revision FROM checkpoints WHERE session_id = ?", (session_id,)
            ).fetchone()
        return int(row[0]) if row is not None else 0


def register() -> None:
    register_checkpoint("sqlite", lambda path="spine.db", **_: SQLiteCheckpoint(path))


register()
