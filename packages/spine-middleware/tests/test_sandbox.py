"""Sandbox middleware: run sync tools in a resource-limited subprocess."""

from __future__ import annotations

import os

import pytest

from spine_core import Agent, tool
from spine_core.testing import ScriptedProvider, calls, text
from spine_middleware import Sandbox

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="sandbox needs POSIX fork")


# Module-level tools so the forked child inherits them (no pickling needed).
@tool
def square(x: int) -> int:
    """Square a number."""
    return x * x


@tool
def hang() -> str:
    """Spin forever (to trip the sandbox timeout)."""
    while True:
        pass


async def test_sandboxed_tool_returns_result() -> None:
    provider = ScriptedProvider(calls(("square", {"x": 6})), text("done"))
    agent = Agent(provider, tools=[square], middleware=[Sandbox(tools=["square"])])
    result = await agent.run("compute")
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert tool_msg.content == "36"
    assert result.answer == "done"


async def test_sandbox_timeout_kills_runaway_tool() -> None:
    provider = ScriptedProvider(calls(("hang", {})), text("recovered"))
    agent = Agent(provider, tools=[hang], middleware=[Sandbox(tools=["hang"], timeout_s=0.3)])
    result = await agent.run("go")
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert "timeout" in (tool_msg.content or "").lower()
    assert result.answer == "recovered"  # runaway tool killed, run continued
