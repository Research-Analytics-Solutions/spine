# spine-middleware

The Spine V1 middleware suite — reliability and shaping, all built on the kernel
hook points (no kernel edits).

| Middleware | Hook(s) | What it does |
|---|---|---|
| `Retry` | `on_error` | Exponential backoff + full jitter on provider errors |
| `ModelFallback` | `on_error` | Switch to the next provider when one fails |
| `LoopGuard` | `after_model` | Stop when the same tool action repeats (`StopReason.LOOP`) |
| `CostTracking` | `after_model` | Fill `cost_usd` from a price table so cost guards bite |
| `Compaction` | `before_model` | Trim long histories non-destructively |
| `StructuredOutput` | `before/after_model` | Validate the final answer against a Pydantic schema, repairing on failure |

```python
from spine_core import Agent, Guards
from spine_middleware import Retry, LoopGuard, CostTracking

agent = Agent(
    "anthropic:claude-sonnet-4-6",
    guards=Guards(max_steps=8, max_cost_usd=0.50),
    middleware=[Retry(max_attempts=3), LoopGuard(window=4), CostTracking(3.0, 15.0)],
)
```

The first five are registered by name (`Retry`, `ModelFallback`, …) so a
`spine.toml` `chain = [...]` resolves them. `StructuredOutput` takes a schema
type and is used from code.
