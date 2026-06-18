"""LoopGuard middleware — halt when the model repeats the same tool action."""

from __future__ import annotations

import json

from spine_core.control import StopRun
from spine_core.middleware import StepContext
from spine_core.result import StopReason

_SCRATCH_KEY = "_loopguard_history"


class LoopGuard:
    """Detect a stuck agent that keeps calling the same tool with the same args.

    Hashes each step's ``(tool, args)`` set; if the same signature appears
    ``max_repeats`` times within the trailing ``window``, the run stops with
    :attr:`StopReason.LOOP` instead of burning the whole step budget.
    """

    def __init__(self, window: int = 4, max_repeats: int = 3) -> None:
        self.window = window
        self.max_repeats = max_repeats

    async def after_model(self, ctx: StepContext) -> None:
        if ctx.response is None or not ctx.response.message.tool_calls:
            return
        signature = json.dumps(
            sorted(
                (c.name, json.dumps(c.arguments, sort_keys=True))
                for c in ctx.response.message.tool_calls
            ),
            sort_keys=True,
        )
        history: list[str] = ctx.state.scratch.setdefault(_SCRATCH_KEY, [])
        history.append(signature)
        recent = history[-self.window :]
        if recent.count(signature) >= self.max_repeats:
            raise StopRun(
                StopReason.LOOP,
                f"loop detected: identical tool action repeated {self.max_repeats}x",
            )
