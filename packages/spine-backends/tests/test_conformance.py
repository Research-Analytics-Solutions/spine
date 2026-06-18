"""Shared CheckpointStore conformance suite — every backend behaves the same."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from spine_backends import RedisCheckpoint, SQLiteCheckpoint
from spine_core import Message, State
from spine_core.checkpoint import InMemoryCheckpointStore


class FakeRedis:
    """Minimal async Redis stand-in (decode_responses=True semantics)."""

    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    async def set(self, key: str, value: str) -> None:
        self._d[key] = value

    async def get(self, key: str) -> str | None:
        return self._d.get(key)

    async def delete(self, key: str) -> None:
        self._d.pop(key, None)


async def _assert_conformance(store: Any) -> None:
    # missing -> None
    assert await store.get("missing") is None

    state = State(session_id="conf")
    state.add_message(Message.user("hello"))
    await store.put(state)

    loaded = await store.get("conf")
    assert loaded is not None
    assert loaded.session_id == "conf"
    assert loaded.messages[0].content == "hello"

    # overwrite round-trips
    state.add_message(Message.assistant("hi back"))
    await store.put(state)
    again = await store.get("conf")
    assert again is not None
    assert len(again.messages) == 2

    await store.delete("conf")
    assert await store.get("conf") is None


@pytest.fixture(params=["memory", "sqlite", "redis"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    if request.param == "memory":
        return InMemoryCheckpointStore()
    if request.param == "sqlite":
        return SQLiteCheckpoint(tmp_path / "conf.db")
    return RedisCheckpoint(client=FakeRedis())


async def test_checkpoint_conformance(store: Any) -> None:
    await _assert_conformance(store)


@pytest.mark.skipif(
    not os.environ.get("SPINE_TEST_PG_DSN"), reason="set SPINE_TEST_PG_DSN to run Postgres test"
)
async def test_postgres_conformance() -> None:
    from spine_backends import PostgresCheckpoint

    store = PostgresCheckpoint(os.environ["SPINE_TEST_PG_DSN"], table="spine_checkpoints_test")
    await _assert_conformance(store)
