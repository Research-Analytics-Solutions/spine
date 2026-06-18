"""MemoryRecall middleware: inject recalled context, persist the exchange."""

from __future__ import annotations

from spine_backends import InMemoryVectorMemory
from spine_core import Agent
from spine_core.messages import Message, ModelResponse, Role, Usage
from spine_middleware import MemoryRecall


class CapturingProvider:
    """Echoes a fixed answer; records the messages it was given."""

    def __init__(self, answer: str = "ok") -> None:
        self.answer = answer
        self.seen: list[Message] = []

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        self.seen = list(messages)
        return ModelResponse(message=Message.assistant(self.answer), usage=Usage())


async def test_recall_injects_relevant_memory() -> None:
    mem = InMemoryVectorMemory()
    await mem.save("The launch code is alpha-seven.")
    await mem.save("Unrelated note about gardening.")

    provider = CapturingProvider("got it")
    agent = Agent(provider, middleware=[MemoryRecall(mem, k=1)])
    await agent.run("what is the launch code?")

    system_msgs = [m for m in provider.seen if m.role is Role.SYSTEM]
    assert any("launch code is alpha-seven" in (m.content or "") for m in system_msgs)
    # injection is ephemeral — not written to durable state
    assert agent.last_result is not None
    assert not any(
        "Relevant memories" in (m.content or "") for m in agent.last_result.state.messages
    )


async def test_run_is_saved_back_to_memory() -> None:
    mem = InMemoryVectorMemory()
    provider = CapturingProvider("the answer is 42")
    agent = Agent(provider, middleware=[MemoryRecall(mem)])
    await agent.run("what is the meaning of life?")

    hits = await mem.search("meaning of life", k=1)
    assert hits
    assert "42" in hits[0].record.content
