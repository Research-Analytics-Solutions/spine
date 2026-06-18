"""Reliability + tooling middlewares: timeout, truncation, breaker, idempotency, rate limit."""

from __future__ import annotations

import time

import anyio

from spine_core import Agent, StopReason, tool
from spine_core.testing import ScriptedProvider, calls, text
from spine_middleware import (
    CircuitBreaker,
    Idempotency,
    RateLimit,
    ToolOutputTruncation,
    ToolTimeout,
)


async def test_tool_timeout_surfaces_error() -> None:
    @tool
    async def slow() -> str:
        """Too slow."""
        await anyio.sleep(1.0)
        return "never"

    provider = ScriptedProvider(calls(("slow", {})), text("done"))
    agent = Agent(provider, tools=[slow], middleware=[ToolTimeout(0.02)])
    result = await agent.run("go")
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert "Error" in (tool_msg.content or "")
    assert result.answer == "done"  # timeout is non-fatal, fed back to the model


async def test_tool_output_truncation() -> None:
    @tool
    async def big() -> str:
        """Huge output."""
        return "x" * 5000

    provider = ScriptedProvider(calls(("big", {})), text("ok"))
    agent = Agent(provider, tools=[big], middleware=[ToolOutputTruncation(max_chars=100)])
    result = await agent.run("go")
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert "truncated" in (tool_msg.content or "")
    assert len(tool_msg.content or "") < 200


async def test_circuit_breaker_opens_and_fails_fast() -> None:
    class AlwaysDown:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            self.calls += 1
            raise RuntimeError("down")

    provider = AlwaysDown()
    breaker = CircuitBreaker(threshold=1, cooldown_s=60.0)
    agent = Agent(provider, middleware=[breaker])

    first = await agent.run("a")
    assert first.stopped_reason is StopReason.ERROR
    assert breaker.open_until > time.monotonic()  # breaker tripped open

    calls_before = provider.calls
    second = await agent.run("b")
    assert second.stopped_reason is StopReason.ERROR
    assert provider.calls == calls_before  # short-circuited: provider not called


async def test_idempotency_runs_side_effect_once() -> None:
    runs: list[int] = []

    @tool
    async def charge(amount: int) -> str:
        """Charge a card."""
        runs.append(amount)
        return f"charged {amount}"

    # model calls the same charge twice across two steps
    provider = ScriptedProvider(
        calls(("charge", {"amount": 10})),
        calls(("charge", {"amount": 10})),
        text("done"),
    )
    agent = Agent(provider, tools=[charge], middleware=[Idempotency(tools=["charge"])])
    result = await agent.run("pay twice")
    assert result.answer == "done"
    assert runs == [10]  # executed once; second call replayed from the idempotency store


async def test_rate_limit_delays_when_empty() -> None:
    # capacity 1 per 0.1s: two model calls in one run must be spaced out
    provider = ScriptedProvider(calls(("noop", {})), text("done"))

    @tool
    async def noop() -> str:
        """No-op."""
        return "ok"

    agent = Agent(provider, tools=[noop], middleware=[RateLimit(max_calls=1, per_s=0.1)])
    started = time.monotonic()
    result = await agent.run("go")
    elapsed = time.monotonic() - started
    assert result.answer == "done"
    assert elapsed >= 0.08  # second model call waited for a token


def test_rate_limit_rejects_bad_config() -> None:
    import pytest

    with pytest.raises(ValueError):
        RateLimit(max_calls=0)
