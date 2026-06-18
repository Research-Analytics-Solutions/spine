"""Tracing — one structured event per kernel transition.

Every step emits a :class:`TraceEvent`, retained in ``Result.trace`` and
streamable live. This is the substrate for deterministic replay and for the
OTel exporter (a middleware that simply listens to these events).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class EventType(str):
    """Well-known event types (string subclass so custom types are allowed)."""

    STEP_START = "step_start"
    MODEL_CALL = "model_call"
    TOKEN = "token"
    MODEL_RESPONSE = "model_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    GUARD_TRIP = "guard_trip"
    INTERRUPT = "interrupt"
    ERROR = "error"
    FINAL = "final"


class TraceEvent(BaseModel):
    """A single immutable record of something the kernel did."""

    seq: int
    type: str
    step: int = 0
    ts: float = Field(default_factory=time.time)
    data: dict[str, Any] = Field(default_factory=dict)


Listener = Callable[[TraceEvent], None]


class Tracer:
    """Collects trace events and optionally fans them out to a live listener."""

    def __init__(self, listener: Listener | None = None) -> None:
        self.events: list[TraceEvent] = []
        self.listener = listener
        self._seq = 0

    def emit(self, type: str, *, step: int = 0, **data: Any) -> TraceEvent:
        event = TraceEvent(seq=self._seq, type=type, step=step, data=data)
        self._seq += 1
        self.events.append(event)
        if self.listener is not None:
            self.listener(event)
        return event
