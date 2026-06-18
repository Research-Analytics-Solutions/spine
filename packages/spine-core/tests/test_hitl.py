"""Human-in-the-loop: durable interrupt + resume (approve / reject / manual)."""

from __future__ import annotations

from spine_core import Agent, Interrupt, StopReason, tool
from spine_core.testing import ScriptedProvider, calls, text

executed: list[str] = []


@tool(approve=True)
async def transfer_funds(amount: int, to: str) -> str:
    """Move money — gated behind human approval."""
    executed.append(f"{amount}->{to}")
    return f"transferred {amount} to {to}"


@tool
async def risky() -> str:
    """A tool that pauses itself for a manual decision."""
    raise Interrupt(payload={"question": "proceed?"})


def setup_function() -> None:
    executed.clear()


async def test_approve_tool_interrupts_then_resumes() -> None:
    provider = ScriptedProvider(
        calls(("transfer_funds", {"amount": 100, "to": "acme"})),
        text("payment sent"),
    )
    agent = Agent(provider, tools=[transfer_funds])

    result = await agent.run("pay invoice 7781")
    assert result.interrupted
    assert result.stopped_reason is StopReason.INTERRUPT
    assert result.resume_token is not None
    assert result.interrupt["tool"] == "transfer_funds"
    assert executed == []  # not run until approved

    resumed = await agent.resume(result.resume_token, decision="approve")
    assert resumed.ok
    assert resumed.answer == "payment sent"
    assert executed == ["100->acme"]


async def test_reject_does_not_execute_tool() -> None:
    provider = ScriptedProvider(
        calls(("transfer_funds", {"amount": 100, "to": "acme"})),
        text("payment cancelled"),
    )
    agent = Agent(provider, tools=[transfer_funds])

    result = await agent.run("pay invoice")
    resumed = await agent.resume(result.resume_token, decision="reject")
    assert resumed.ok
    assert executed == []
    tool_msg = next(m for m in resumed.state.messages if m.role.value == "tool")
    assert "rejected" in (tool_msg.content or "")


async def test_resume_survives_a_fresh_agent_via_shared_checkpoint() -> None:
    # Simulate a process restart: a brand-new Agent with the same checkpoint store.
    from spine_core.checkpoint import InMemoryCheckpointStore

    store = InMemoryCheckpointStore()
    provider = ScriptedProvider(
        calls(("transfer_funds", {"amount": 5, "to": "bob"})),
        text("ok"),
    )
    agent1 = Agent(provider, tools=[transfer_funds], checkpoint=store)
    result = await agent1.run("pay bob")
    session_id = result.state.session_id

    agent2 = Agent(provider, tools=[transfer_funds], checkpoint=store)
    # Resume by session id (resume token map is process-local; the checkpoint is not).
    resumed = await agent2.resume(session_id, decision="approve")
    assert resumed.ok
    assert executed == ["5->bob"]


async def test_manual_interrupt_decision_becomes_tool_result() -> None:
    provider = ScriptedProvider(calls(("risky", {})), text("handled"))
    agent = Agent(provider, tools=[risky])

    result = await agent.run("do the risky thing")
    assert result.interrupted
    assert result.interrupt == {"question": "proceed?"}

    resumed = await agent.resume(result.resume_token, decision="go ahead")
    assert resumed.ok
    tool_msg = next(m for m in resumed.state.messages if m.role.value == "tool")
    assert tool_msg.content == "go ahead"
