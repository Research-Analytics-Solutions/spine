"""Orchestration: sequential pipeline, supervisor routing, handoff transfer."""

from __future__ import annotations

from spine_core import Agent
from spine_core.messages import Message, ModelResponse, Usage
from spine_core.testing import ScriptedProvider, calls, text
from spine_orchestration import Handoff, Sequential, supervisor


class CapturingProvider:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.last_input: str | None = None

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        for m in reversed(messages):
            if m.role.value == "user":
                self.last_input = m.content
                break
        return ModelResponse(message=Message.assistant(self.answer), usage=Usage())


async def test_sequential_pipes_answers() -> None:
    p2 = CapturingProvider("SECOND")
    a1 = Agent(ScriptedProvider(text("FIRST")))
    a2 = Agent(p2)
    result = await Sequential(a1, a2).run("start")
    assert result.answer == "SECOND"
    assert p2.last_input == "FIRST"  # got agent1's answer as input


async def test_supervisor_routes_to_worker() -> None:
    worker = Agent(ScriptedProvider(text("billing handled")), name="billing")
    boss_provider = ScriptedProvider(
        calls(("billing", {"input": "fix invoice"})),
        text("done by supervisor"),
    )
    boss = supervisor("x", {"billing": worker}, provider=boss_provider)
    result = await boss.run("my invoice is wrong")
    assert result.answer == "done by supervisor"
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert tool_msg.content == "billing handled"


async def test_handoff_transfers_to_peer() -> None:
    triage_provider = ScriptedProvider(
        calls(("transfer_to_specialist", {"reason": "needs expert"})),
        text("triage filler (discarded)"),
    )
    specialist_provider = ScriptedProvider(text("specialist resolved it"))
    triage = Agent(triage_provider, name="triage")
    specialist = Agent(specialist_provider, name="specialist")

    team = Handoff({"triage": triage, "specialist": specialist}, start="triage")
    result = await team.run("help me")

    assert result.answer == "specialist resolved it"
    assert team.path == ["triage", "specialist"]


async def test_handoff_no_transfer_returns_first() -> None:
    a = Agent(ScriptedProvider(text("handled directly")), name="a")
    b = Agent(ScriptedProvider(text("unused")), name="b")
    team = Handoff({"a": a, "b": b}, start="a")
    result = await team.run("simple")
    assert result.answer == "handled directly"
    assert team.path == ["a"]
