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
    # the *second* model call must actually see the tool result fed back in
    second_call = provider.calls[1]
    assert any(m.role.value == "tool" and m.content == "4" for m in second_call)


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


async def test_stream_emits_token_events() -> None:
    agent = Agent(ScriptedProvider(text("hello there world")))
    events = [e async for e in agent.stream("hi")]
    tokens = [e.data["delta"] for e in events if e.type == "token"]
    assert "".join(tokens).strip() == "hello there world"
    assert agent.last_result is not None
    assert agent.last_result.answer == "hello there world"


def test_sync_facade() -> None:
    agent = Agent(ScriptedProvider(text("sync works")))
    result = agent.run_sync("hi")
    assert result.answer == "sync works"


async def test_parallel_tool_calls_run_concurrently() -> None:
    import anyio

    order: list[str] = []

    @tool
    async def slow() -> str:
        """Slow tool."""
        await anyio.sleep(0.05)
        order.append("slow")
        return "slow-done"

    @tool
    async def fast() -> str:
        """Fast tool."""
        order.append("fast")
        return "fast-done"

    provider = ScriptedProvider(calls(("slow", {}), ("fast", {})), text("done"))
    agent = Agent(provider, tools=[slow, fast], parallel_tools=True)
    result = await agent.run("do both")

    assert result.answer == "done"
    # fast finished before slow despite being requested second -> concurrent
    assert order == ["fast", "slow"]
    # results appended in call order regardless of completion order
    tool_msgs = [m for m in result.state.messages if m.role.value == "tool"]
    assert [m.content for m in tool_msgs] == ["slow-done", "fast-done"]


async def test_cooperative_cancellation() -> None:
    provider = ScriptedProvider(calls(("add", {"a": 1, "b": 1})), repeat=True)
    flips = {"n": 0}

    def should_cancel() -> bool:
        flips["n"] += 1
        return flips["n"] > 2  # cancel after a couple of steps

    agent = Agent(provider, tools=[add], guards=Guards(max_steps=100))
    result = await agent.run("loop", should_cancel=should_cancel)
    assert result.stopped_reason is StopReason.CANCELLED
    assert result.state.step >= 1  # work was checkpointed, run is resumable


async def test_agent_as_tool_delegation() -> None:
    sub = Agent(ScriptedProvider(text("subagent says hi")), name="greeter")
    parent_provider = ScriptedProvider(
        calls(("greeter", {"input": "say hi"})),
        text("the greeter replied"),
    )
    parent = Agent(parent_provider, tools=[sub.as_tool()])
    result = await parent.run("delegate")
    assert result.answer == "the greeter replied"
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert tool_msg.content == "subagent says hi"


async def test_run_scope_hooks_bracket_the_run() -> None:
    from spine_core import Result, State

    events: list[str] = []

    class RecordingMW:
        async def on_run_start(self, state: State) -> None:
            events.append(f"start:{state.session_id}")

        async def before_model(self, ctx: StepContext) -> None:
            events.append("before_model")

        async def on_run_end(self, state: State, result: Result) -> None:
            events.append(f"end:{result.stopped_reason.value}")

    agent = Agent(ScriptedProvider(text("ok")), middleware=[RecordingMW()])
    result = await agent.run("hi")
    # start brackets the whole run; end fires once, after the model work, with result
    assert events[0].startswith("start:")
    assert "before_model" in events
    assert events[-1] == "end:final"
    assert events.count(events[-1]) == 1
    assert result.ok


def test_unregistered_provider_errors() -> None:
    from spine_core import ProviderError

    with pytest.raises(ProviderError):
        Agent("unknown:model")


async def test_retry_loop_is_bounded_by_timeout() -> None:
    # A misbehaving middleware that retries forever must not loop forever: the
    # wall-clock guard is re-checked inside the provider retry loop.
    import anyio

    class SlowFailing:
        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            await anyio.sleep(0.02)
            raise RuntimeError("still down")

    class AlwaysRetry:
        async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction:
            return ErrorAction.RETRY

    agent = Agent(SlowFailing(), middleware=[AlwaysRetry()], guards=Guards(timeout_s=0.05))
    result = await agent.run("hang forever")
    assert result.stopped_reason is StopReason.TIMEOUT


async def test_retry_loop_is_bounded_by_attempt_cap() -> None:
    # With no timeout, the hard attempt cap still stops an infinite retry.
    class InstantFail:
        def __init__(self) -> None:
            self.attempts = 0

        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            self.attempts += 1
            raise RuntimeError("nope")

    class AlwaysRetry:
        async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction:
            return ErrorAction.RETRY

    provider = InstantFail()
    agent = Agent(provider, middleware=[AlwaysRetry()], guards=Guards(timeout_s=None))
    result = await agent.run("retry forever")
    assert result.stopped_reason is StopReason.ERROR
    assert "retry cap" in (result.error or "")
    assert provider.attempts <= 101  # cap is 100, not unbounded
