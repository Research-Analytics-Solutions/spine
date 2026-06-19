# Middleware catalog

All middlewares live in `spine-middleware` and are built purely on the kernel
[hook points](../concepts/middleware.md). The first group is registered by name
for `spine.toml` chains.

## Execution & reliability

| Middleware | Hook(s) | What it does |
|---|---|---|
| `Retry(max_attempts, base, factor, jitter)` | `on_error` | Exponential backoff + full jitter on provider errors |
| `ModelFallback(*providers)` | `on_error` | Switch to the next provider when one fails |
| `LoopGuard(window, max_repeats)` | `after_model` | Stop when the same tool action repeats (`StopReason.LOOP`) |
| `CircuitBreaker(threshold, cooldown_s)` | `before/after_model`, `on_error` | Open after N failures; fail fast for a cooldown |
| `RateLimit(max_calls, per_s)` | `before_model` | Per-process token-bucket on model calls |

## Cost, caching & shaping

| Middleware | Hook(s) | What it does |
|---|---|---|
| `CostTracking(input_per_mtok, output_per_mtok)` | `after_model` | Fill `cost_usd` from a price table so cost guards bite |
| `Cache(ttl_s, max_size)` | `before/after_model` | Serve an identical request from a content-hashed cache (free on hit) |
| `Compaction(max_messages, keep_last)` | `before_model` | Trim long histories non-destructively |
| `StructuredOutput(schema, max_repairs)` | `before/after_model` | Validate the final answer vs a Pydantic schema, repairing on failure |

## Tools

| Middleware | Hook(s) | What it does |
|---|---|---|
| `ToolTimeout(timeout_s, tools=...)` | `before_tool` | Per-tool wall-clock timeout (kernel cancels) |
| `ToolOutputTruncation(max_chars)` | `after_tool` | Cap huge tool outputs before re-feeding context |
| `Idempotency(tools=..., store=...)` | `before/after_tool` | Run a side-effecting tool once per `(tool, args)` |
| `Sandbox(tools=..., timeout_s, max_cpu_s, max_memory_mb)` | `before_tool` | Run a sync tool in a resource-limited subprocess (POSIX) |

## Safety & multi-tenancy

| Middleware | Hook(s) | What it does |
|---|---|---|
| `PIIRedaction(entities=...)` | `after_tool`, `after_model` | Redact PII from tool output, traces, and final answer |
| `PromptInjectionScreen(action="annotate"\|"block")` | `after_tool` | Treat tool output as untrusted data |
| `ContentPolicy(banned=..., validate=...)` | `before/after_model` | Block input/output (`StopReason.GUARDRAIL`) |
| `TenantBudget(max_cost_usd, max_tokens)` | `before/after_model` | Cumulative per-tenant ceiling across runs |

## Memory & replay

| Middleware | Hook(s) | What it does |
|---|---|---|
| `MemoryRecall(memory, k, scope_session)` | `before_model`, `on_run_end` | Inject recalled memories; persist the exchange |
| `Recorder()` / `Replayer(recording)` | record / replay | Deterministic replay of model + tool outputs |

## Observability

| Middleware | Hook(s) | What it does |
|---|---|---|
| `ConsoleLogger()` | all hooks | Opt-in pretty terminal log of each step/tool/result (Rich if installed) |
| `OTelMiddleware(tracer=...)` (from `spine-otel`) | run/model/tool spans | One OpenTelemetry span tree per run |

See [Guardrails & safety](../guides/guardrails.md) and [Middleware
concepts](../concepts/middleware.md) for usage and ordering.
