"""Checkpoint store — durable serialization of ``State`` for resume.

Distinct from *memory* (semantic recall): a checkpoint store exists purely so a
run can survive a crash, a restart, or a multi-day HITL pause. The protocol is
tiny so SQLite/Postgres/Redis backends drop in unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from spine_core.state import State


@runtime_checkable
class CheckpointStore(Protocol):
    """Persist and recover run state by session id."""

    async def put(self, state: State) -> None: ...
    async def get(self, session_id: str) -> State | None: ...
    async def delete(self, session_id: str) -> None: ...


class InMemoryCheckpointStore:
    """Default, process-local store. Durable backends replace this in prod."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def put(self, state: State) -> None:
        # Round-trip through JSON so behavior matches a real serializing backend.
        self._store[state.session_id] = state.model_dump_json()

    async def get(self, session_id: str) -> State | None:
        raw = self._store.get(session_id)
        return State.model_validate_json(raw) if raw is not None else None

    async def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)
