"""Guards — hard, always-on ceilings enforced inside the kernel loop.

Guards are the reason a runaway loop is *structurally impossible* in Spine:
the check runs every iteration, in the core, and cannot be bypassed by a
misbehaving middleware. Every limit is opt-in (``None`` means no ceiling).
"""

from __future__ import annotations

from pydantic import BaseModel

from spine_core.result import StopReason
from spine_core.state import State


class Guards(BaseModel):
    """Declarative limits checked before each step."""

    max_steps: int | None = 12
    max_cost_usd: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    max_depth: int | None = 8  # sub-agent delegation depth

    def check(self, state: State, elapsed_s: float) -> StopReason | None:
        """Return the tripped :class:`StopReason`, or ``None`` to continue.

        Checked in priority order so the most specific budget wins the report.
        """
        if self.max_depth is not None and state.depth > self.max_depth:
            return StopReason.MAX_DEPTH
        if self.max_steps is not None and state.step >= self.max_steps:
            return StopReason.MAX_STEPS
        if self.max_cost_usd is not None and state.usage.cost_usd >= self.max_cost_usd:
            return StopReason.MAX_COST
        if self.max_tokens is not None and state.usage.total_tokens >= self.max_tokens:
            return StopReason.MAX_TOKENS
        if self.timeout_s is not None and elapsed_s >= self.timeout_s:
            return StopReason.TIMEOUT
        return None
