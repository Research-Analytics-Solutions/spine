# Middleware

A middleware is an object implementing any subset of the [hook
points](kernel.md#hook-points). The kernel composes them into an onion; order is
explicit and inspectable. **Every feature outside the kernel is a middleware, a
backend, or an adapter** — if a feature needs to edit the kernel, it was modeled
wrong.

## Writing one

Subclass `Middleware` (no-op defaults) or just implement the hooks you need:

```python
from spine_core import Middleware, StepContext

class Logging(Middleware):
    async def before_model(self, ctx: StepContext) -> None:
        print(f"step {ctx.state.step}: {len(ctx.messages)} messages")

    async def after_model(self, ctx: StepContext) -> None:
        print("usage:", ctx.response.usage)
```

```python
agent = Agent("openai:gpt-4o-mini", middleware=[Logging()])
```

## Order matters

`before_*` hooks run outermost-first (list order); `after_*` hooks run
innermost-first (reverse). A wrapping middleware brackets the ones it encloses.

```python
middleware=[Retry(), Guardrails(), Compaction(), OTel()]
#           outer ───────────────────────────► inner   (before_model)
#           inner ◄─────────────────────────── outer   (after_model)
```

## Control flow

Middleware can steer the run, not just observe it:

- **Stop the run** — raise `StopRun(reason, message)`; the kernel turns it into a
  clean stopped `Result` (used by `LoopGuard`, guardrails, budgets).
- **Force another turn** — set `ctx.force_continue = True` to loop again even
  without a tool call (used by `StructuredOutput` for repair).
- **Short-circuit the provider** — preset `ctx.response` in `before_model` (used
  by `Cache` and `Replayer`).
- **Skip / preset a tool** — set `ctx.skip` + `ctx.result` in `before_tool` (used
  by `Idempotency`, `Replayer`, `Sandbox`).
- **Handle errors** — `on_error` returns `retry` / `fallback` / `skip` / `fail`
  (used by `Retry`, `ModelFallback`, `CircuitBreaker`).

## Configure by name

Registered middlewares resolve from `spine.toml`:

```toml
[spine.middleware]
chain = ["Retry", "CostTracking", "LoopGuard"]

[spine.plugins.CostTracking]
input_per_mtok = 0.15
output_per_mtok = 0.60
```

See the full [middleware catalog](../reference/middleware.md).
