"""OpenTelemetry middleware — emits one span tree per agent run.

A ``spine.run`` span brackets the whole run (via the ``on_run_start`` /
``on_run_end`` hooks); each model call and tool call nests under it as a child
span. Spans carry token counts, cost, latency, model, finish reason, and tool
name as attributes — following the OTel GenAI semantic conventions where they
exist — so any OTLP backend (Grafana, Datadog, Langfuse, Phoenix) lights up with
no Spine-specific tooling.
"""

from __future__ import annotations

import time

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from spine_core.middleware import ErrorAction, StepContext, ToolContext
from spine_core.result import Result, StopReason
from spine_core.state import State

_GENAI_SYSTEM = "gen_ai.system"
_GENAI_MODEL = "gen_ai.request.model"
_GENAI_IN = "gen_ai.usage.input_tokens"
_GENAI_OUT = "gen_ai.usage.output_tokens"
_GENAI_FINISH = "gen_ai.response.finish_reason"


class OTelMiddleware:
    """Bridges Spine's hook points to OpenTelemetry spans.

    Construct with a configured ``Tracer`` (or rely on the global provider).
    One instance is safe to share across concurrent runs: per-run state is keyed
    by session id, and tool spans by ``session:tool_call_id``.
    """

    def __init__(self, tracer: Tracer | None = None) -> None:
        self._tracer: Tracer = tracer or trace.get_tracer("spine-otel")
        self._runs: dict[str, tuple[Span, object]] = {}
        self._models: dict[str, Span] = {}  # one in-flight model call per run
        self._tools: dict[str, Span] = {}

    # -- run scope ----------------------------------------------------------

    async def on_run_start(self, state: State) -> None:
        span = self._tracer.start_span(
            "spine.run", attributes={"spine.session_id": state.session_id}
        )
        token = otel_context.attach(trace.set_span_in_context(span))
        self._runs[state.session_id] = (span, token)

    async def on_run_end(self, state: State, result: Result) -> None:
        # Sweep a model span left open by a terminal error (the kernel returns
        # from the provider call before after_model on a fatal failure).
        leaked = self._models.pop(state.session_id, None)
        if leaked is not None:
            leaked.set_status(Status(StatusCode.ERROR, result.error or "model call failed"))
            leaked.end()

        entry = self._runs.pop(state.session_id, None)
        if entry is None:
            return
        span, token = entry
        span.set_attribute("spine.stopped_reason", result.stopped_reason.value)
        span.set_attribute("spine.steps", state.step)
        span.set_attribute(_GENAI_IN, state.usage.input_tokens)
        span.set_attribute(_GENAI_OUT, state.usage.output_tokens)
        span.set_attribute("spine.cost_usd", state.usage.cost_usd)
        if result.stopped_reason is StopReason.ERROR:
            span.set_status(Status(StatusCode.ERROR, result.error or "run failed"))
        else:
            span.set_status(Status(StatusCode.OK))
        span.end()
        otel_context.detach(token)  # type: ignore[arg-type]

    # -- model calls --------------------------------------------------------

    async def before_model(self, ctx: StepContext) -> None:
        span = self._tracer.start_span("spine.model")
        span.set_attribute("spine.step", ctx.state.step)
        self._models[ctx.state.session_id] = span
        ctx.extra["otel_t0"] = time.monotonic()

    async def after_model(self, ctx: StepContext) -> None:
        span = self._models.pop(ctx.state.session_id, None)
        if span is None:
            return
        response = ctx.response
        if response is not None:
            span.set_attribute(_GENAI_SYSTEM, "spine")
            span.set_attribute(_GENAI_IN, response.usage.input_tokens)
            span.set_attribute(_GENAI_OUT, response.usage.output_tokens)
            span.set_attribute("spine.cost_usd", response.usage.cost_usd)
            span.set_attribute("spine.tool_calls", len(response.message.tool_calls))
            if response.finish_reason:
                span.set_attribute(_GENAI_FINISH, response.finish_reason)
        span.end()

    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction | None:
        span = self._models.get(ctx.state.session_id)
        if span is not None:
            span.record_exception(err)  # span is closed by after_model / on_run_end
        return None  # observe only; never change control flow

    # -- tool calls ---------------------------------------------------------

    async def before_tool(self, ctx: ToolContext) -> None:
        span = self._tracer.start_span(
            f"spine.tool.{ctx.call.name}",
            attributes={"spine.tool.name": ctx.call.name},
        )
        self._tools[self._tool_key(ctx)] = span

    async def after_tool(self, ctx: ToolContext) -> None:
        span = self._tools.pop(self._tool_key(ctx), None)
        if span is None:
            return
        if ctx.error is not None:
            span.record_exception(ctx.error)
            span.set_status(Status(StatusCode.ERROR, str(ctx.error)))
        else:
            span.set_status(Status(StatusCode.OK))
        span.end()

    @staticmethod
    def _tool_key(ctx: ToolContext) -> str:
        return f"{ctx.state.session_id}:{ctx.call.id}"


def configure_otlp(
    endpoint: str | None = None,
    *,
    service_name: str = "spine",
) -> OTelMiddleware:
    """Convenience: wire a global OTLP-HTTP exporter and return the middleware.

    Requires the ``otlp`` extra (``uv add 'spine-otel[otlp]'``). For tests or
    custom pipelines, construct ``OTelMiddleware(tracer=...)`` directly instead.
    """
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return OTelMiddleware(trace.get_tracer("spine-otel"))
