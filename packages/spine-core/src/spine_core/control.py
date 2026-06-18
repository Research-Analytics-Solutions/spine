"""Control-flow signals a middleware can raise to steer the kernel.

These are how policy middleware (LoopGuard, Guardrails, budget enforcers) halt a
run cleanly — the kernel converts a :class:`StopRun` into a normal
:class:`~spine_core.result.Result` with the carried stop reason, rather than
letting an exception escape ``agent.run()``.
"""

from __future__ import annotations

from spine_core.errors import SpineError
from spine_core.result import StopReason


class StopRun(SpineError):
    """Raised by a middleware hook to end the run with a structured reason.

    ``message`` becomes the answer for non-error reasons (e.g. a guardrail
    explanation) or the error text when ``reason`` is :attr:`StopReason.ERROR`.
    """

    def __init__(self, reason: StopReason = StopReason.GUARDRAIL, message: str = "") -> None:
        super().__init__(message or reason.value)
        self.reason = reason
        self.message = message
