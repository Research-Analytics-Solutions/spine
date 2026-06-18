# Build a middleware

A middleware is any object implementing one or more [hook
points](../concepts/kernel.md#hook-points). No base class is required — the kernel
calls a hook only if you define it (subclass `Middleware` for no-op defaults and
editor help).

## The hooks

```python
class Middleware:
    async def on_run_start(self, state): ...
    async def on_run_end(self, state, result): ...
    async def before_model(self, ctx): ...     # StepContext
    async def after_model(self, ctx): ...       # StepContext
    async def before_tool(self, ctx): ...       # ToolContext
    async def after_tool(self, ctx): ...         # ToolContext
    async def on_error(self, ctx, err): ...      # -> ErrorAction | None
```

What each context exposes is in the [data model](../reference/data-model.md#what-middleware-sees).

## A worked example: a stopwatch + budget logger

```python exec="1" source="above" result="text"
import time
from spine_core import Agent, Middleware, StepContext
from spine_core.testing import ScriptedProvider, text

class Stopwatch(Middleware):
    async def before_model(self, ctx: StepContext) -> None:
        ctx.extra["t0"] = time.perf_counter()

    async def after_model(self, ctx: StepContext) -> None:
        dt = time.perf_counter() - ctx.extra["t0"]
        print(f"step {ctx.state.step}: {dt*1000:.1f}ms, {ctx.state.usage.total_tokens} tok")

agent = Agent(ScriptedProvider(text("done")), middleware=[Stopwatch()])
agent.run_sync("hi")
```

## Steering the run (not just observing)

| To… | Do this | In hook |
|---|---|---|
| Stop the run cleanly | `raise StopRun(StopReason.GUARDRAIL, "why")` | any |
| Loop again without a tool call | `ctx.force_continue = True` | `after_model` |
| Serve a cached/recorded response | set `ctx.response` | `before_model` |
| Rewrite the prompt | reassign `ctx.messages` | `before_model` |
| Swap provider | set `ctx.provider` | `before_model` / `on_error` |
| Skip a tool & preset its result | `ctx.skip = True; ctx.result = ...` | `before_tool` |
| Add a per-tool timeout | `ctx.timeout_s = 5` | `before_tool` |
| Retry / fallback on error | `return ErrorAction.RETRY` / `FALLBACK` | `on_error` |

!!! tip "Per-middleware scratch"
    Use `ctx.extra` (a dict on `StepContext`) for your own per-step state, and
    `ctx.state.scratch` for state that should persist into the checkpoint.

## Make it configurable by name

Register it so `spine.toml` chains and `resolve_middleware` can find it:

```python
from spine_core import register_middleware

register_middleware("Stopwatch", Stopwatch)
```

Now:

```toml
[spine.middleware]
chain = ["Stopwatch", "Retry"]
```

Constructor kwargs come from `[spine.plugins.Stopwatch]`.

## Ordering

`before_*` runs in list order (outer→inner); `after_*` runs reversed
(inner→outer). Put guards/limits **outer** so they bracket everything; put
response rewriters where their effect should land. See [Middleware
concepts](../concepts/middleware.md#order-matters).

## Ship it

Package it as `spine-mw-<name>` with an entry point and it becomes installable for
anyone — see [Publish a plugin](publish.md).
