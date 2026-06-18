"""MemoryRecall middleware — inject relevant long-term memories, store the run.

Recall is non-destructive: matched memories are prepended to the model's view of
the conversation for the first step only (``ctx.messages`` is reassigned, not the
durable history). After the run, the question/answer pair is saved back.
"""

from __future__ import annotations

from spine_core.memory import Memory
from spine_core.messages import Message, Role
from spine_core.middleware import StepContext
from spine_core.result import Result, StopReason
from spine_core.state import State

_RECALLED = "_memory_recalled"


class MemoryRecall:
    """Search a :class:`Memory` for context and persist the exchange."""

    def __init__(
        self,
        memory: Memory,
        *,
        k: int = 3,
        scope_session: bool = False,
        min_score: float = 0.0,
        store_results: bool = True,
    ) -> None:
        self.memory = memory
        self.k = k
        self.scope_session = scope_session
        self.min_score = min_score
        self.store_results = store_results

    @staticmethod
    def _last_user(messages: list[Message]) -> str | None:
        for message in reversed(messages):
            if message.role is Role.USER:
                return message.content
        return None

    async def before_model(self, ctx: StepContext) -> None:
        if ctx.state.scratch.get(_RECALLED):
            return
        ctx.state.scratch[_RECALLED] = True
        query = self._last_user(ctx.messages)
        if not query:
            return
        session = ctx.state.session_id if self.scope_session else None
        hits = await self.memory.search(query, k=self.k, session_id=session)
        snippets = [h.record.content for h in hits if h.score >= self.min_score]
        if not snippets:
            return
        recall = Message.system("Relevant memories:\n" + "\n".join(f"- {s}" for s in snippets))
        ctx.messages = [recall, *ctx.messages]  # ephemeral: not persisted to state

    async def on_run_end(self, state: State, result: Result) -> None:
        if not self.store_results or result.stopped_reason is not StopReason.FINAL:
            return
        question = self._last_user(state.messages)
        if question and result.answer:
            await self.memory.save(
                f"Q: {question}\nA: {result.answer}", session_id=state.session_id
            )
