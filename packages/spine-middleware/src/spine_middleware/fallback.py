"""ModelFallback middleware — switch providers when one errors."""

from __future__ import annotations

from spine_core.middleware import ErrorAction, StepContext
from spine_core.provider import Provider, resolve_provider


class ModelFallback:
    """On a provider error, swap to the next provider and retry the call.

    Providers are tried in order, per step, until one succeeds or the list is
    exhausted (then the kernel fails). Accepts ``Provider`` instances or
    ``"scheme:model"`` strings.
    """

    def __init__(self, *providers: str | Provider) -> None:
        if not providers:
            raise ValueError("ModelFallback needs at least one fallback provider")
        self._providers: list[Provider] = [
            resolve_provider(p) if isinstance(p, str) else p for p in providers
        ]

    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction | None:
        index: int = ctx.extra.get("fallback_index", 0)
        if index >= len(self._providers):
            return ErrorAction.FAIL
        ctx.provider = self._providers[index]
        ctx.extra["fallback_index"] = index + 1
        return ErrorAction.FALLBACK
