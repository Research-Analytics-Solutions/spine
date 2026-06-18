"""Redis checkpoint backend — durable state for distributed workers.

The ``redis`` client is imported lazily and may be injected (tests use a fake),
so importing this module never requires the dependency or a server.
"""

from __future__ import annotations

import json
from typing import Any

from spine_backends.migrations import migrate
from spine_core.registry import register_checkpoint
from spine_core.state import State


class RedisCheckpoint:
    """Durable :class:`~spine_core.checkpoint.CheckpointStore` over Redis."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        *,
        client: Any = None,
        prefix: str = "spine:checkpoint:",
    ) -> None:
        self.url = url
        self.prefix = prefix
        self._client = client

    def _ensure_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    async def put(self, state: State) -> None:
        await self._ensure_client().set(self._key(state.session_id), state.model_dump_json())

    async def get(self, session_id: str) -> State | None:
        raw = await self._ensure_client().get(self._key(session_id))
        if raw is None:
            return None
        return State.model_validate(migrate(json.loads(raw)))

    async def delete(self, session_id: str) -> None:
        await self._ensure_client().delete(self._key(session_id))


def register() -> None:
    register_checkpoint("redis", lambda url="redis://localhost:6379", **_: RedisCheckpoint(url))


register()
