"""OTel middleware: span tree shape, attributes, error status, no leaks."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from spine_core import Agent, tool
from spine_core.testing import ScriptedProvider, calls, text
from spine_otel import OTelMiddleware


@tool
async def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
async def boom() -> str:
    """Always explodes."""
    raise ValueError("kaboom")


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    return exp


def _mw(exporter: InMemorySpanExporter) -> OTelMiddleware:
    # Build a tracer bound to this test's exporter.
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return OTelMiddleware(tracer=provider.get_tracer("test"))


def _by_name(spans: list) -> dict[str, list]:
    out: dict[str, list] = {}
    for span in spans:
        out.setdefault(span.name, []).append(span)
    return out


async def test_run_produces_a_span_tree(exporter: InMemorySpanExporter) -> None:
    provider = ScriptedProvider(calls(("add", {"a": 2, "b": 2})), text("done"))
    agent = Agent(provider, tools=[add], middleware=[_mw(exporter)])
    result = await agent.run("add it")
    assert result.ok

    spans = exporter.get_finished_spans()
    names = _by_name(spans)
    assert "spine.run" in names
    assert "spine.model" in names
    assert "spine.tool.add" in names

    run_span = names["spine.run"][0]
    # model + tool spans are children of the run span
    for child_name in ("spine.model", "spine.tool.add"):
        for child in names[child_name]:
            assert child.parent is not None
            assert child.parent.span_id == run_span.context.span_id

    assert run_span.attributes["spine.stopped_reason"] == "final"
    assert run_span.attributes["spine.steps"] == 2
    assert run_span.attributes["spine.session_id"] == result.state.session_id
    assert run_span.status.status_code is StatusCode.OK


async def test_model_span_carries_genai_attributes(exporter: InMemorySpanExporter) -> None:
    agent = Agent(ScriptedProvider(text("hi")), middleware=[_mw(exporter)])
    await agent.run("hello")
    model = _by_name(exporter.get_finished_spans())["spine.model"][0]
    assert model.attributes["gen_ai.usage.input_tokens"] == 10
    assert model.attributes["gen_ai.usage.output_tokens"] == 5
    assert model.attributes["gen_ai.system"] == "spine"
    assert model.attributes["spine.tool_calls"] == 0


async def test_tool_failure_sets_error_status(exporter: InMemorySpanExporter) -> None:
    provider = ScriptedProvider(calls(("boom", {})), text("recovered"))
    agent = Agent(provider, tools=[boom], middleware=[_mw(exporter)])
    await agent.run("blow up")
    tool_span = _by_name(exporter.get_finished_spans())["spine.tool.boom"][0]
    assert tool_span.status.status_code is StatusCode.ERROR
    assert any(e.name == "exception" for e in tool_span.events)


async def test_provider_failure_ends_all_spans_with_error(exporter: InMemorySpanExporter) -> None:
    class AlwaysFails:
        async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
            raise RuntimeError("provider down")

    agent = Agent(AlwaysFails(), middleware=[_mw(exporter)])
    result = await agent.run("doomed")
    assert result.stopped_reason.value == "error"

    spans = exporter.get_finished_spans()
    names = _by_name(spans)
    # the model span must NOT leak: it is ended (swept) even though after_model
    # never ran, and both run + model spans report ERROR.
    assert "spine.model" in names
    assert names["spine.model"][0].status.status_code is StatusCode.ERROR
    assert names["spine.run"][0].status.status_code is StatusCode.ERROR
    # every started span is finished (no leaks)
    assert all(span.end_time is not None for span in spans)
