"""Retry middleware — exponential backoff + jitter on provider errors."""

from __future__ import annotations

import random

import anyio

from spine_core.middleware import ErrorAction, StepContext


class Retry:
    """Retry a failed model call with capped exponential backoff.

    Implemented purely via the ``on_error`` hook: the kernel re-issues the call
    on ``RETRY`` and gives up on ``FAIL``. ``ctx.attempt`` is the count of
    retries already performed this step.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        *,
        base: float = 0.1,
        factor: float = 2.0,
        max_delay: float = 10.0,
        jitter: bool = True,
    ) -> None:
        self.max_attempts = max_attempts
        self.base = base
        self.factor = factor
        self.max_delay = max_delay
        self.jitter = jitter

    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction | None:
        if ctx.attempt + 1 >= self.max_attempts:
            return ErrorAction.FAIL
        delay = min(self.max_delay, self.base * (self.factor**ctx.attempt))
        if self.jitter:
            delay = random.uniform(0, delay)  # full jitter
        if delay > 0:
            await anyio.sleep(delay)
        return ErrorAction.RETRY
