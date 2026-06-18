"""Reliability middlewares — circuit breaker, idempotency, rate limiting."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import anyio

from spine_core.control import StopRun
from spine_core.middleware import ErrorAction, StepContext, ToolContext
from spine_core.result import StopReason


class CircuitBreaker:
    """Open the circuit after repeated provider failures; fail fast while open.

    Counts failures via ``on_error``; once ``threshold`` consecutive failures is
    reached the breaker opens for ``cooldown_s``, during which ``before_model``
    short-circuits the run with a guardrail-style error. A successful model call
    resets the count.
    """

    def __init__(
        self,
        *,
        threshold: int = 5,
        cooldown_s: float = 30.0,
        message: str = "circuit breaker open: too many recent failures",
    ) -> None:
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.message = message
        self.failures = 0
        self.open_until = 0.0

    async def before_model(self, ctx: StepContext) -> None:
        if time.monotonic() < self.open_until:
            raise StopRun(StopReason.ERROR, self.message)

    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction | None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.monotonic() + self.cooldown_s
        return None  # observe only; let other middleware decide retry policy

    async def after_model(self, ctx: StepContext) -> None:
        self.failures = 0  # a success closes the circuit


class Idempotency:
    """De-duplicate side-effecting tool calls by an idempotency key.

    On a repeated ``(tool, args)`` the cached result is replayed and the tool is
    not executed again (``ctx.skip``). Restrict to side-effecting tools with
    ``tools=[...]`` and share ``store`` across processes for cross-worker safety.
    """

    def __init__(
        self,
        *,
        tools: list[str] | None = None,
        store: dict[str, Any] | None = None,
        key: Callable[[str, dict[str, Any]], str] | None = None,
    ) -> None:
        self.tools = set(tools) if tools else None
        self._store = store if store is not None else {}
        self._key_fn = key

    def _applies(self, name: str) -> bool:
        return self.tools is None or name in self.tools

    def _key(self, name: str, args: dict[str, Any]) -> str:
        if self._key_fn is not None:
            return self._key_fn(name, args)
        return f"{name}:{json.dumps(args, sort_keys=True, default=str)}"

    async def before_tool(self, ctx: ToolContext) -> None:
        if not self._applies(ctx.call.name):
            return
        key = self._key(ctx.call.name, ctx.args)
        if key in self._store:
            ctx.result = self._store[key]
            ctx.skip = True

    async def after_tool(self, ctx: ToolContext) -> None:
        if not self._applies(ctx.call.name) or ctx.skip:
            return
        self._store[self._key(ctx.call.name, ctx.args)] = ctx.result


class RateLimit:
    """Token-bucket rate limit on model calls (per-process).

    ``max_calls`` per ``per_s`` seconds; refills continuously. When empty,
    ``before_model`` waits for a token. For cross-worker limiting back this with
    a shared store (e.g. Redis) — that is a separate distributed backend.
    """

    def __init__(self, max_calls: int, per_s: float = 1.0) -> None:
        if max_calls <= 0 or per_s <= 0:
            raise ValueError("max_calls and per_s must be positive")
        self.capacity = float(max_calls)
        self.rate = max_calls / per_s  # tokens per second
        self.tokens = float(max_calls)
        self.updated = time.monotonic()
        self._lock = anyio.Lock()

    async def before_model(self, ctx: StepContext) -> None:
        async with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < 1.0:
                await anyio.sleep((1.0 - self.tokens) / self.rate)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0
