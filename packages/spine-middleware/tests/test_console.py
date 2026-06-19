"""ConsoleLogger: prints a readable run log to its console."""

from __future__ import annotations

import io

from rich.console import Console

from spine_core import Agent, tool
from spine_core.testing import ScriptedProvider, calls, text
from spine_middleware import ConsoleLogger


@tool
async def add(a: int, b: int) -> int:
    """Add."""
    return a + b


async def test_console_logger_emits_lines() -> None:
    buf = io.StringIO()
    logger = ConsoleLogger(console=Console(file=buf, width=100, no_color=True))
    provider = ScriptedProvider(calls(("add", {"a": 2, "b": 3})), text("5"))
    await Agent(provider, tools=[add], middleware=[logger]).run("add 2 and 3")

    out = buf.getvalue()
    assert "run" in out  # on_run_start
    assert "model" in out  # before/after_model
    assert "add" in out  # tool call + result
    assert "final" in out  # on_run_end stop reason


async def test_console_logger_plain_fallback_no_crash() -> None:
    # No console + Rich present still works; just ensure a run completes cleanly.
    agent = Agent(ScriptedProvider(text("ok")), middleware=[ConsoleLogger()])
    result = await agent.run("hi")
    assert result.ok
