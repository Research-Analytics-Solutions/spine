"""Multi-tenancy — per-tenant cost/token budgets enforced across runs.

The budget is keyed by ``state.tenant_id`` and accumulates across every run that
shares the (optionally external) ``store``, so a single tenant cannot exceed its
ceiling even across many sessions or workers.
"""

from __future__ import annotations

from spine_core.control import StopRun
from spine_core.middleware import StepContext
from spine_core.result import StopReason

_DEFAULT_TENANT = "_default"


class TenantBudget:
    """Enforce a cumulative per-tenant spend ceiling (cost and/or tokens)."""

    def __init__(
        self,
        *,
        max_cost_usd: float | None = None,
        max_tokens: int | None = None,
        store: dict[str, dict[str, float]] | None = None,
        message: str = "tenant budget exceeded",
    ) -> None:
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens
        self.message = message
        self._spend = store if store is not None else {}

    def _bucket(self, tenant_id: str | None) -> dict[str, float]:
        return self._spend.setdefault(tenant_id or _DEFAULT_TENANT, {"cost": 0.0, "tokens": 0.0})

    def spend(self, tenant_id: str | None) -> dict[str, float]:
        """Current accumulated spend for a tenant."""
        return dict(self._bucket(tenant_id))

    async def before_model(self, ctx: StepContext) -> None:
        bucket = self._bucket(ctx.state.tenant_id)
        if self.max_cost_usd is not None and bucket["cost"] >= self.max_cost_usd:
            raise StopRun(StopReason.MAX_COST, self.message)
        if self.max_tokens is not None and bucket["tokens"] >= self.max_tokens:
            raise StopRun(StopReason.MAX_TOKENS, self.message)

    async def after_model(self, ctx: StepContext) -> None:
        if ctx.response is None:
            return
        bucket = self._bucket(ctx.state.tenant_id)
        bucket["cost"] += ctx.response.usage.cost_usd
        bucket["tokens"] += ctx.response.usage.total_tokens
