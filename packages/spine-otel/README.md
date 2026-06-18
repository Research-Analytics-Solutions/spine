# spine-otel

OpenTelemetry middleware for Spine. Emits **one span tree per run**: a
`spine.run` parent span with `spine.model` and `spine.tool.<name>` children.

```python
from spine_core import Agent
from spine_otel import configure_otlp

# ships spans to an OTLP collector (needs the `otlp` extra)
agent = Agent("anthropic:claude-sonnet-4-6", middleware=[configure_otlp("http://localhost:4318/v1/traces")])
```

Or bring your own tracer:

```python
from spine_otel import OTelMiddleware
agent = Agent(provider, middleware=[OTelMiddleware(tracer=my_tracer)])
```

Span attributes follow the OTel GenAI semantic conventions
(`gen_ai.usage.input_tokens`, `gen_ai.response.finish_reason`, …) plus
`spine.cost_usd`, `spine.steps`, `spine.stopped_reason`, so existing dashboards
work unchanged.

Install: `uv add spine-otel` (middleware) or `uv add 'spine-otel[otlp]'` (with the
OTLP-HTTP exporter).
