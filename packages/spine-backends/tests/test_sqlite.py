"""SQLite checkpoint: round-trip, revision, durable cross-restart HITL, migration."""

from __future__ import annotations

from pathlib import Path

from spine_backends import SQLiteCheckpoint, register_migration
from spine_backends.migrations import migrate
from spine_core import Agent, Message, State, tool
from spine_core.testing import ScriptedProvider, calls, text

executed: list[int] = []


@tool(approve=True)
async def transfer(amount: int) -> str:
    """Move money — needs approval."""
    executed.append(amount)
    return f"sent {amount}"


def setup_function() -> None:
    executed.clear()


async def test_round_trip_revision_and_delete(tmp_path: Path) -> None:
    store = SQLiteCheckpoint(tmp_path / "s.db")
    state = State(session_id="x")
    state.add_message(Message.user("hi"))

    await store.put(state)
    got = await store.get("x")
    assert got is not None
    assert got.messages[0].content == "hi"
    assert await store.revision("x") == 1

    await store.put(state)  # second write bumps the optimistic-lock revision
    assert await store.revision("x") == 2

    await store.delete("x")
    assert await store.get("x") is None
    assert await store.revision("missing") == 0


async def test_durable_hitl_resume_across_restart(tmp_path: Path) -> None:
    db = tmp_path / "runs.db"
    provider = ScriptedProvider(calls(("transfer", {"amount": 50})), text("done"))

    agent1 = Agent(provider, tools=[transfer], checkpoint=SQLiteCheckpoint(db))
    paused = await agent1.run("pay invoice")
    assert paused.interrupted
    session_id = paused.state.session_id

    # Simulate a process restart: a brand-new store + agent over the same file.
    agent2 = Agent(provider, tools=[transfer], checkpoint=SQLiteCheckpoint(db))
    resumed = await agent2.resume(session_id, decision="approve")
    assert resumed.ok
    assert executed == [50]


def test_migrate_pass_through_at_current_version() -> None:
    assert migrate({"version": 1, "session_id": "x"})["version"] == 1


def test_migrate_runs_registered_upgrade() -> None:
    def v0_to_v1(raw: dict) -> dict:
        raw = dict(raw)
        raw["version"] = 1
        raw.setdefault("session_id", "migrated")
        return raw

    register_migration(0, v0_to_v1)
    out = migrate({"version": 0})
    assert out["version"] == 1
    assert out["session_id"] == "migrated"
