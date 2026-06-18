# spine-core

The Spine kernel: the tiny, load-bearing runtime everything else plugs into.

Zero heavy dependencies (Pydantic v2 + anyio). It owns exactly the reliability
runtime — the step loop, explicit serializable state, always-on guards, the
tracer, and the hook points (middleware / provider / tool / checkpoint
protocols). Features live in plugins, never in the kernel.

## 3-line quickstart

```python
from spine_core import Agent
from spine_core.testing import ScriptedProvider, text

agent = Agent(ScriptedProvider(text("hello from spine")))
result = agent.run_sync("hi")
print(result.answer)  # -> "hello from spine"
```

## Guarantees

- **No hidden prompts** — every model call consumes inspectable `Message` objects.
- **No runaway loops** — `Guards` are checked every iteration, inside the kernel.
- **Deterministic trace** — every transition emits a `TraceEvent` in `Result.trace`.
- **Durable HITL** — an approval pause returns a `resume_token` backed by a checkpoint.

See the repository root `CLAUDE.md` for the full architecture & delivery plan.
