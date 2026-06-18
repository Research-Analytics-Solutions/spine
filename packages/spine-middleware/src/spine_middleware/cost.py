"""CostTracking middleware — fill in USD cost from a price table."""

from __future__ import annotations

from spine_core.middleware import StepContext


class CostTracking:
    """Compute ``cost_usd`` from token counts and a per-1M-token price.

    Runs in ``after_model`` (before the kernel banks usage), so the computed
    cost feeds straight into the cost guard. By default it only fills a cost the
    provider left at zero; set ``overwrite=True`` to always recompute.
    """

    def __init__(
        self,
        input_per_mtok: float,
        output_per_mtok: float,
        *,
        overwrite: bool = False,
    ) -> None:
        self.input_per_mtok = input_per_mtok
        self.output_per_mtok = output_per_mtok
        self.overwrite = overwrite

    async def after_model(self, ctx: StepContext) -> None:
        if ctx.response is None:
            return
        usage = ctx.response.usage
        if usage.cost_usd and not self.overwrite:
            return
        usage.cost_usd = (
            usage.input_tokens * self.input_per_mtok + usage.output_tokens * self.output_per_mtok
        ) / 1_000_000
