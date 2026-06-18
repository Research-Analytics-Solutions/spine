"""Deterministic replay: record a run, replay it without provider or tools."""

from __future__ import annotations

from spine_core import Agent, tool
from spine_core.testing import ScriptedProvider, calls, text
from spine_middleware import Recorder, Replayer

counters = {"tool": 0}


@tool
async def act() -> str:
    """Side-effecting tool that counts how often it really runs."""
    counters["tool"] += 1
    return f"live-{counters['tool']}"


class Boom:
    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        raise AssertionError("provider must not be called during replay")


def setup_function() -> None:
    counters["tool"] = 0


async def test_record_then_replay_reproduces_run() -> None:
    provider = ScriptedProvider(calls(("act", {})), text("final answer"))
    recorder = Recorder()
    recorded = await Agent(provider, tools=[act], middleware=[recorder]).run("go")

    assert recorded.answer == "final answer"
    assert counters["tool"] == 1
    recording = recorder.recording()

    # Replay with a provider that would explode and a tool that would re-run:
    replayed = await Agent(Boom(), tools=[act], middleware=[Replayer(recording)]).run("go")

    assert replayed.answer == "final answer"
    assert counters["tool"] == 1  # tool NOT executed again — result came from the recording
    tool_msg = next(m for m in replayed.state.messages if m.role.value == "tool")
    assert tool_msg.content == "live-1"  # the recorded result


async def test_replayer_accepts_recorder_directly() -> None:
    provider = ScriptedProvider(text("hi"))
    recorder = Recorder()
    await Agent(provider, middleware=[recorder]).run("x")
    replayed = await Agent(Boom(), middleware=[Replayer(recorder)]).run("x")
    assert replayed.answer == "hi"
