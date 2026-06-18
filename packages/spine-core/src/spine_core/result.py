"""Run result + structured stop reasons.

A run never just "ends" — it stops for an enumerable reason. Callers branch on
``stopped_reason`` rather than guessing from a null answer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from spine_core.messages import Usage
from spine_core.state import State
from spine_core.trace import TraceEvent


class StopReason(StrEnum):
    FINAL = "final"  # model produced an answer with no further tool calls
    MAX_STEPS = "max_steps"
    MAX_COST = "max_cost"
    MAX_TOKENS = "max_tokens"
    TIMEOUT = "timeout"
    MAX_DEPTH = "max_depth"
    INTERRUPT = "interrupt"  # paused for human-in-the-loop; resumable
    ERROR = "error"
    CANCELLED = "cancelled"


class Result(BaseModel):
    """The outcome of an ``agent.run()`` / ``agent.resume()`` call."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    answer: str | None = None
    stopped_reason: StopReason = StopReason.FINAL
    state: State
    trace: list[TraceEvent] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    # Set only when stopped_reason is INTERRUPT.
    resume_token: str | None = None
    interrupt: Any = None
    # Set only when stopped_reason is ERROR.
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.stopped_reason == StopReason.FINAL

    @property
    def interrupted(self) -> bool:
        return self.stopped_reason == StopReason.INTERRUPT
