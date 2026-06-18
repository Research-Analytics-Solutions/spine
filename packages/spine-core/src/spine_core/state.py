"""Explicit, serializable run state.

The kernel is stateless between steps; everything needed to resume a run lives
here. Because ``State`` is plain Pydantic, it round-trips to JSON for durable
checkpointing and horizontal scale (Design Principle: observable & explicit).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from spine_core.messages import Message, ToolCall, Usage

# Bumped when the on-disk shape changes; checkpoint backends migrate on read.
STATE_VERSION = 1


class RunStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class PendingApproval(BaseModel):
    """A tool call paused awaiting a human decision (HITL).

    ``mode`` distinguishes a kernel-enforced approval gate (``approve`` tool)
    from a tool that raised :class:`~spine_core.interrupt.Interrupt` itself.
    """

    call: ToolCall
    mode: str = "approve"  # "approve" | "manual"
    payload: Any = None


class State(BaseModel):
    """The complete, resumable state of one agent run."""

    version: int = STATE_VERSION
    session_id: str
    messages: list[Message] = Field(default_factory=list)
    step: int = 0
    usage: Usage = Field(default_factory=Usage)
    status: RunStatus = RunStatus.RUNNING
    depth: int = 0  # sub-agent delegation depth (guarded against cycles)
    pending: PendingApproval | None = None
    scratch: dict[str, Any] = Field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def add_usage(self, usage: Usage) -> None:
        self.usage = self.usage + usage
