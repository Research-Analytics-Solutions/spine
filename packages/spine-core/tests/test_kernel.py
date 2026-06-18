"""Kernel behavior: loop, tools, guards, validation, errors, streaming."""

from __future__ import annotations

import pytest

from spine_core import Agent, ErrorAction, Guards, StepContext, StopReason, tool
from spine_core.testing import ScriptedProvider, calls, text


@tool
async def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


async def test_basic_final_answer() -> None:
    agent = Agent(ScriptedProvider(text("the answer is 4")))
    result = await agent.run("what is 2+2?")
    assert result.ok
    assert result.stopped_reason is StopReason.FINAL
    assert result.answer == "the answer is 4"
    assert result.usage.total_tokens == 15


async def test_tool_call_then_answer() -> None:
    provider = ScriptedProvider(
        calls(("add", {"a": 2, "b": 2})),
        text("2 + 2 = 4"),
    )
    agent = Agent(provider, tools=[add])
    result = await agent.run("add 2 and 2")
    assert result.answer == "2 + 2 = 4"
    # user, assistant(toolcall), tool result, assistant(final)
    tool_msgs = [m for m in result.state.messages if m.role.value == "tool"]
    assert tool_msgs[0].content == "4"


async def test_arg_validation_feeds_error_back() -> None:
    provider = ScriptedProvider(
        calls(("add", {"a": "not-an-int", "b": 2})),
        text("recovered"),
    )
    agent = Agent(provider, tools=[add])
    result = await agent.run("break it")
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert "Error" in (tool_msg.content or "")
    assert result.answer == "recovered"


async def test_unknown_tool_is_not_fatal() -> None:
    provider = ScriptedProvider(calls(("nope", {})), text("ok"))
    agent = Agent(provider, tools=[add])
    result = await agent.run("call missing tool")
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert "unknown tool" in (tool_msg.content or "")


async def test_guard_max_steps_stops_runaway() -> None:
    # Provider always asks to call the tool again -> would loop forever.
    provider = ScriptedProvider(calls(("add", {"a": 1, "b": 1})), repeat=True)
    agent = Agent(provider, tools=[add], guards=Guards(max_steps=3))
    result = await agent.run("loop forever")
    assert result.stopped_reason is StopReason.MAX_STEPS
    assert result.state.step == 3


async def test_guard_max_cost() -> None:
    provider = ScriptedProvider(calls(("add", {"a": 1, "b": 1}), cost_usd=0.30), repeat=True)
    agent = Agent(provider, tools=[add], guards=Guards(max_steps=100, max_cost_usd=0.50))
    result = await agent.run("spend money")
    assert result.stopped_reason is StopReason.MAX_COST


async def test_on_error_retry_then_succeed() -> None:
    class FlakyProvider:
        def __init__(self) -> None:
            self.attempts = 0

        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            self.attempts += 1
            if self.attempts < 3:
                raise RuntimeError("503 overloaded")
            return text("recovered after retries")

    class RetryMW:
        def __init__(self, max_attempts: int) -> None:
            self.max_attempts = max_attempts

        async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction:
            if ctx.attempt + 1 < self.max_attempts:
                return ErrorAction.RETRY
            return ErrorAction.FAIL

    provider = FlakyProvider()
    agent = Agent(provider, middleware=[RetryMW(max_attempts=5)])
    result = await agent.run("be flaky")
    assert result.ok
    assert provider.attempts == 3


async def test_on_error_exhausted_fails() -> None:
    class AlwaysFails:
        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            raise RuntimeError("permanent failure")

    agent = Agent(AlwaysFails())
    result = await agent.run("doomed")
    assert result.stopped_reason is StopReason.ERROR
    assert "permanent failure" in (result.error or "")


async def test_streaming_emits_events() -> None:
    provider = ScriptedProvider(calls(("add", {"a": 1, "b": 2})), text("done"))
    agent = Agent(provider, tools=[add])
    types = [event.type async for event in agent.stream("stream it")]
    assert "step_start" in types
    assert "tool_call" in types
    assert "final" in types
    assert agent.last_result is not None
    assert agent.last_result.answer == "done"


def test_sync_facade() -> None:
    agent = Agent(ScriptedProvider(text("sync works")))
    result = agent.run_sync("hi")
    assert result.answer == "sync works"


@pytest.mark.parametrize("bad_model", ["unknown:model"])
def test_unregistered_provider_errors(bad_model: str) -> None:
    from spine_core import ProviderError

    with pytest.raises(ProviderError):
        Agent(bad_model)
