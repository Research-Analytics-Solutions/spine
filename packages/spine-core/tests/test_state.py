"""State serialization, guards math, and tool schema derivation."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from spine_core import Guards, Message, State, StopReason, Usage, tool
from spine_core.state import STATE_VERSION


def test_state_round_trips_through_json() -> None:
    state = State(session_id="s1")
    state.add_message(Message.user("hello"))
    state.add_message(Message.assistant("hi"))
    state.add_usage(Usage(input_tokens=10, output_tokens=3, cost_usd=0.01))

    restored = State.model_validate_json(state.model_dump_json())
    assert restored == state
    assert restored.version == STATE_VERSION
    assert restored.usage.total_tokens == 13


@given(
    steps=st.integers(min_value=0, max_value=50),
    max_steps=st.integers(min_value=1, max_value=20),
)
def test_guard_max_steps_is_monotonic(steps: int, max_steps: int) -> None:
    state = State(session_id="s")
    state.step = steps
    trip = Guards(max_steps=max_steps).check(state, elapsed_s=0.0)
    if steps >= max_steps:
        assert trip is StopReason.MAX_STEPS
    else:
        assert trip is None


def test_guards_all_none_never_trip() -> None:
    state = State(session_id="s")
    state.step = 10_000
    state.add_usage(Usage(input_tokens=10**9, cost_usd=10**6))
    guards = Guards(
        max_steps=None, max_cost_usd=None, max_tokens=None, timeout_s=None, max_depth=None
    )
    assert guards.check(state, elapsed_s=10**6) is None


async def test_raw_tool_passes_args_through_to_callable() -> None:
    from spine_core import raw_tool

    seen: dict = {}

    async def invoke(**kwargs: object) -> str:
        seen.update(kwargs)
        return "ran"

    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    t = raw_tool("search", "Search.", schema, invoke)
    assert t.parameters == schema
    # no Python signature to validate against: args pass through untouched
    assert t.validate({"q": "spine", "extra": 1}) == {"q": "spine", "extra": 1}
    result = await t.call({"q": "spine"})
    assert result == "ran"
    assert seen == {"q": "spine"}


def test_tool_schema_derived_from_type_hints() -> None:
    @tool
    def lookup(query: str, limit: int = 10) -> str:
        """Look something up."""
        return query

    assert lookup.name == "lookup"
    assert lookup.description == "Look something up."
    props = lookup.parameters["properties"]
    assert props["query"]["type"] == "string"
    assert props["limit"]["default"] == 10
    assert "query" in lookup.parameters["required"]
    assert "limit" not in lookup.parameters.get("required", [])
