# Tracing, streaming & replay

## Trace

Every step emits a structured `TraceEvent`, retained in `Result.trace`. No hidden
state, no hidden prompts.

```python
result = await agent.run("…")
for event in result.trace:
    print(event.seq, event.type, event.data)
```

Event types: `step_start`, `model_call`, `token`, `model_response`, `tool_call`,
`tool_result`, `guard_trip`, `interrupt`, `error`, `final`.

!!! note "The kernel never prints"
    Spine writes nothing to stdout or `logging` — traces are **data**, not console
    spam. To get a readable log in your terminal, opt in with the `ConsoleLogger`
    middleware:

    ```python
    from spine_middleware import ConsoleLogger
    agent = Agent("openai:gpt-4o-mini", middleware=[ConsoleLogger()])
    ```
    ```
    11:02:19 spine ▶ run    531df530
    11:02:19 spine → model  step 1 · 1 msg
    11:02:19 spine ⚙ tool   add(a=17, b=25)
    11:02:19 spine ✓ tool   add → 42
    11:02:19 spine ■ done   final · 2 steps · $0.00012
    ```

    It is **opt-in** — the kernel prints nothing unless you add `ConsoleLogger`.
    Options: `ConsoleLogger(prefix="myagent", timestamp=False)`.

## Live streaming

`agent.stream()` yields trace events as they happen — including `token` deltas
when the provider streams:

```python
async for event in agent.stream("write a haiku"):
    if event.type == "token":
        print(event.data["delta"], end="", flush=True)
print()
print(agent.last_result.answer)
```

The CLI wraps this: `spine dev "your prompt"`.

## OpenTelemetry

The OTel middleware emits one **span tree per run** — a `spine.run` parent with
`spine.model` and `spine.tool.<name>` children — attributed per the GenAI semantic
conventions plus `spine.cost_usd`, `spine.steps`, `spine.stopped_reason`. Any OTLP
backend (Grafana, Datadog, Langfuse, Phoenix) lights up with no Spine-specific
tooling.

```python
from spine_otel import configure_otlp

agent = Agent("openai:gpt-4o-mini", middleware=[configure_otlp("http://localhost:4318/v1/traces")])
```

## Deterministic replay

The only non-determinism in a run is model responses and tool results. `Recorder`
captures both; `Replayer` serves them back — reproducing a run step-for-step
**without calling the provider or any tool**.

```python
from spine_middleware import Recorder, Replayer

recorder = Recorder()
await Agent(provider, tools=tools, middleware=[recorder]).run("go")
recording = recorder.recording()  # JSON-serializable

# later — exact replay, no network, no side effects
await Agent(provider, tools=tools, middleware=[Replayer(recording)]).run("go")
```

This is the basis for golden-trace regression tests.
