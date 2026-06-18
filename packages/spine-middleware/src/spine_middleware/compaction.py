"""Compaction middleware — keep the context window from overflowing."""

from __future__ import annotations

from spine_core.messages import Message, Role
from spine_core.middleware import StepContext


class Compaction:
    """Trim long histories before each model call, non-destructively.

    When the message count exceeds ``max_messages``, system messages plus the
    last ``keep_last`` turns are kept and the middle is replaced by one synthetic
    note. ``ctx.messages`` is reassigned (not mutated), so the full history stays
    in durable state and is re-compacted fresh each step. A leading orphan tool
    result is dropped to keep the trimmed window valid for providers.
    """

    def __init__(self, max_messages: int = 40, keep_last: int = 20) -> None:
        if keep_last >= max_messages:
            raise ValueError("keep_last must be smaller than max_messages")
        self.max_messages = max_messages
        self.keep_last = keep_last

    async def before_model(self, ctx: StepContext) -> None:
        messages = ctx.messages
        if len(messages) <= self.max_messages:
            return

        system = [m for m in messages if m.role is Role.SYSTEM]
        tail = [m for m in messages[-self.keep_last :] if m.role is not Role.SYSTEM]
        while tail and tail[0].role is Role.TOOL:
            tail = tail[1:]  # never start the window on an orphaned tool result

        dropped = len(messages) - len(system) - len(tail)
        if dropped <= 0:
            return
        note = Message.system(f"[{dropped} earlier messages compacted to fit the context window]")
        ctx.messages = [*system, note, *tail]
