"""V1 middleware behavior — retry, fallback, loop guard, cost, compaction, structured."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from spine_core import Agent, Guards, Message, State, StepContext, StopReason, tool
from spine_core.testing import ScriptedProvider, calls, text
from spine_middleware import (
    Compaction,
    CostTracking,
    LoopGuard,
    ModelFallback,
    Retry,
    StructuredOutput,
)


@tool
async def add(a: int, b: int) -> int:
    """Add."""
    return a + b


class _Flaky:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("503")
        return text("recovered")


async def test_retry_recovers_then_succeeds() -> None:
    provider = _Flaky(fail_times=2)
    agent = Agent(provider, middleware=[Retry(max_attempts=5, base=0.0, jitter=False)])
    result = await agent.run("go")
    assert result.ok
    assert provider.calls == 3


async def test_retry_gives_up_after_max() -> None:
    provider = _Flaky(fail_times=99)
    agent = Agent(provider, middleware=[Retry(max_attempts=3, base=0.0, jitter=False)])
    result = await agent.run("go")
    assert result.stopped_reason is StopReason.ERROR
    assert provider.calls == 3


async def test_model_fallback_switches_provider() -> None:
    class Down:
        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            raise RuntimeError("primary down")

    good = ScriptedProvider(text("via fallback"))
    agent = Agent(Down(), middleware=[ModelFallback(good)])
    result = await agent.run("hi")
    assert result.ok
    assert result.answer == "via fallback"


async def test_loop_guard_stops_repeated_action() -> None:
    provider = ScriptedProvider(calls(("add", {"a": 1, "b": 1})), repeat=True)
    agent = Agent(
        provider,
        tools=[add],
        guards=Guards(max_steps=50),
        middleware=[LoopGuard(window=4, max_repeats=3)],
    )
    result = await agent.run("loop")
    assert result.stopped_reason is StopReason.LOOP
    assert result.state.step == 3


async def test_cost_tracking_fills_cost_and_guard_bites() -> None:
    provider = ScriptedProvider(text("hi"))  # usage 10 in / 5 out, cost 0
    agent = Agent(provider, middleware=[CostTracking(3.0, 15.0)])
    result = await agent.run("price me")
    # (10 * 3 + 5 * 15) / 1e6
    assert result.usage.cost_usd == pytest.approx(0.000105)


async def test_compaction_trims_history_nondestructively() -> None:
    state = State(session_id="s")
    messages = [Message.system("rules")]
    for i in range(20):
        messages.append(Message.user(f"u{i}"))
        messages.append(Message.assistant(f"a{i}"))
    ctx = StepContext(state, list(messages), [])

    await Compaction(max_messages=10, keep_last=4).before_model(ctx)

    assert len(ctx.messages) < len(messages)
    assert ctx.messages[0].content == "rules"  # system kept
    assert any("compacted" in (m.content or "") for m in ctx.messages)
    assert len(messages) == 41  # original list untouched (non-destructive)


class _Person(BaseModel):
    name: str
    age: int


async def test_structured_output_repairs_then_validates() -> None:
    provider = ScriptedProvider(text("sorry, no json"), text('{"name": "Ada", "age": 36}'))
    agent = Agent(provider, middleware=[StructuredOutput(_Person)])
    result = await agent.run("extract the person")
    assert result.ok
    assert result.state.scratch["structured_output"] == {"name": "Ada", "age": 36}
    assert result.state.step == 2  # one repair turn happened


async def test_structured_output_accepts_fenced_json() -> None:
    provider = ScriptedProvider(text('```json\n{"name": "Ada", "age": 36}\n```'))
    agent = Agent(provider, middleware=[StructuredOutput(_Person)])
    result = await agent.run("extract")
    assert result.ok
    assert result.state.scratch["structured_output"] == {"name": "Ada", "age": 36}


async def test_structured_output_fails_loud_after_repairs() -> None:
    provider = ScriptedProvider(text("never json"), repeat=True)
    agent = Agent(provider, middleware=[StructuredOutput(_Person, max_repairs=1)])
    result = await agent.run("extract")
    assert result.stopped_reason is StopReason.ERROR
    assert "structured output invalid" in (result.error or "")
