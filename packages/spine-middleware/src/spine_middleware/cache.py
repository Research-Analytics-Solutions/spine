"""Cache middleware — serve a model response for an identical request.

Keys on a content hash of the messages + available tool names, so a hit only
happens for a genuinely identical request (edge case §10.1: keys include the
content hash; TTL is respected). On a hit the provider is never called — the
kernel skips it because ``before_model`` preset ``ctx.response``.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from spine_core.messages import ModelResponse, Usage
from spine_core.middleware import StepContext


class Cache:
    """In-memory prompt/response cache with optional TTL and size bound.

    A hit returns a deep copy (so downstream mutation can't corrupt the entry)
    and, by default, zeroes usage — a cached response is free, which lets cost
    guards and reports reflect the saving. Pass a dict-like ``store`` to share a
    cache across agents.
    """

    def __init__(
        self,
        *,
        ttl_s: float | None = None,
        max_size: int = 1024,
        zero_cost_on_hit: bool = True,
        store: dict[str, tuple[ModelResponse, float | None]] | None = None,
    ) -> None:
        self.ttl_s = ttl_s
        self.max_size = max_size
        self.zero_cost_on_hit = zero_cost_on_hit
        self._store = store if store is not None else {}
        self.hits = 0
        self.misses = 0

    def _key(self, ctx: StepContext) -> str:
        payload: dict[str, Any] = {
            "messages": [m.model_dump(mode="json") for m in ctx.messages],
            "tools": sorted(t.name for t in ctx.tools),
        }
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    async def before_model(self, ctx: StepContext) -> None:
        key = self._key(ctx)
        ctx.extra["cache_key"] = key
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return
        response, expires = entry
        if expires is not None and time.time() >= expires:
            self._store.pop(key, None)
            self.misses += 1
            return
        self.hits += 1
        ctx.extra["cache_hit"] = True
        hit = response.model_copy(deep=True)
        if self.zero_cost_on_hit:
            hit = hit.model_copy(update={"usage": Usage()})
        ctx.response = hit

    async def after_model(self, ctx: StepContext) -> None:
        if ctx.extra.get("cache_hit") or ctx.response is None:
            return
        key = ctx.extra.get("cache_key")
        if key is None:
            return
        if len(self._store) >= self.max_size and key not in self._store:
            self._store.pop(next(iter(self._store)), None)  # evict oldest (FIFO)
        expires = time.time() + self.ttl_s if self.ttl_s is not None else None
        self._store[key] = (ctx.response.model_copy(deep=True), expires)
