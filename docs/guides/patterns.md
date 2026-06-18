# Patterns & edge cases

Production workarounds for the hard cases.

## Long conversations that blow the context window

Trim history before each model call, non-destructively (the full history stays in
durable state and is re-trimmed each step):

```python
from spine_middleware import Compaction

agent = Agent("openai:gpt-4o-mini", middleware=[Compaction(max_messages=40, keep_last=20)])
```

A leading orphan tool result is dropped so the trimmed window stays valid for the
provider.

## Strict cost control

Cost guards stop *before the next* step, so a run can overshoot by one in-flight
call. To keep a hard cap, combine a low `max_cost_usd` with `max_tokens` and a
tight `max_steps`, and make sure cost is measured:

```python
from spine_core import Guards
from spine_middleware import CostTracking

agent = Agent(
    "openai:gpt-4o-mini",
    guards=Guards(max_steps=4, max_cost_usd=0.05, max_tokens=8000),
    middleware=[CostTracking(0.15, 0.60)],   # needed for non-native price tables
)
```

## Resilient model calls: retry → fallback → breaker

Order matters — these are independent middlewares that compose:

```python
from spine_middleware import Retry, ModelFallback, CircuitBreaker

agent = Agent(
    "openai:gpt-4o-mini",
    middleware=[
        CircuitBreaker(threshold=5, cooldown_s=30),  # stop hammering a dead provider
        Retry(max_attempts=3, base=0.2),             # transient errors
        ModelFallback("anthropic:claude-sonnet-4-6"),# last resort: switch provider
    ],
)
```

The kernel also caps provider attempts (100/step) and re-checks the wall-clock
timeout inside the retry loop, so a misbehaving middleware can't loop forever.

## Don't double-charge on retries

Make side-effecting tools idempotent so a retry replays the cached result instead
of running the effect twice:

```python
from spine_middleware import Idempotency

agent = Agent("openai:gpt-4o-mini", tools=[charge_card],
              middleware=[Idempotency(tools=["charge_card"])])
```

## Graceful shutdown (SIGTERM)

Pass a cancel predicate; the kernel finishes and checkpoints the current step,
then returns `cancelled` — resume later from exactly there:

```python
import signal
stopping = False
signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__("stopping", True))

result = await agent.run(task, should_cancel=lambda: stopping)
if result.stopped_reason.value == "cancelled":
    ...  # state is checkpointed; another worker can resume result.state.session_id
```

## HITL that outlives the process

The resume token is the session id, backed by the checkpoint store. A brand-new
process resumes a days-old pause:

```python
from spine_backends import SQLiteCheckpoint

store = SQLiteCheckpoint("runs.db")
# process A pauses for approval → record res.resume_token (== session_id)
# process B (next day): same store
res = await Agent("openai:gpt-4o-mini", tools=[refund], checkpoint=store).resume(token, "approve")
```

## Huge tool outputs

```python
from spine_middleware import ToolOutputTruncation

agent = Agent("openai:gpt-4o-mini", tools=[scrape],
              middleware=[ToolOutputTruncation(max_chars=4000)])
```

## Runaway / untrusted tool code

```python
from spine_middleware import Sandbox

# sync tools only; resource limits (CPU/mem) + wall timeout; POSIX
agent = Agent("openai:gpt-4o-mini", tools=[run_user_code],
              middleware=[Sandbox(tools=["run_user_code"], timeout_s=5, max_memory_mb=256)])
```

This stops runaway CPU/memory/hangs. For *security* isolation of untrusted code,
use a container/VM.

## Stop on repeated actions

```python
from spine_middleware import LoopGuard

agent = Agent("openai:gpt-4o-mini", tools=tools, middleware=[LoopGuard(window=4, max_repeats=3)])
# stops with StopReason.LOOP if the same (tool, args) repeats
```

## Golden-trace regression tests

Record a run once; replay it forever with no network and no side effects — assert
the answer is byte-stable:

```python
from spine_middleware import Recorder, Replayer

rec = Recorder()
gold = await Agent(provider, tools=tools, middleware=[rec]).run("task")
recording = rec.recording()   # save to a fixture file

# in CI — deterministic, offline
out = await Agent(provider, tools=tools, middleware=[Replayer(recording)]).run("task")
assert out.answer == gold.answer
```

## Concurrent sessions on one agent

An `Agent` is safe to reuse across concurrent runs — each `run()` with no
`session_id` gets a fresh `State`. Stateful middleware (LoopGuard, OTel, …) keys by
session id, so sessions don't interfere. For a shared `ScriptedProvider` in tests,
keep `concurrency=1` (its index is mutable).

## Per-tenant isolation & budgets

```python
from spine_middleware import TenantBudget

budget = TenantBudget(max_cost_usd=10.0)   # cumulative, per tenant, across runs
agent = Agent("openai:gpt-4o-mini", middleware=[budget], tenant_id="acme")
```

## Custom stop conditions

Any middleware can end a run cleanly:

```python
from spine_core import Middleware, StepContext, StopRun, StopReason

class MaxToolCalls(Middleware):
    def __init__(self, limit: int) -> None:
        self.limit, self.seen = limit, 0
    async def after_model(self, ctx: StepContext) -> None:
        self.seen += len(ctx.response.message.tool_calls)
        if self.seen > self.limit:
            raise StopRun(StopReason.GUARDRAIL, f"too many tool calls (>{self.limit})")
```

## Force another turn

Set `ctx.force_continue = True` in `after_model` to loop again even when the model
produced a plain answer — the basis of repair loops (see `StructuredOutput`).
