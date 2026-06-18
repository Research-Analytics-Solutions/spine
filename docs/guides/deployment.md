# Deployment & scale

Spine runs the same kernel across three shapes — only backend config differs.
Because `State` is fully serializable and the kernel is stateless between steps,
horizontal scale is "add workers."

## 1. Embedded

Imported into an app or script. In-memory or SQLite checkpoint.

```python
from spine_backends import SQLiteCheckpoint
agent = Agent("openai:gpt-4o-mini", checkpoint=SQLiteCheckpoint("runs.db"))
```

## 2. Server

Behind an async API (e.g. FastAPI). Postgres checkpoint, Redis rate limiter.

```python
from spine_backends import PostgresCheckpoint
from spine_middleware import RateLimit

agent = Agent(
    "openai:gpt-4o-mini",
    checkpoint=PostgresCheckpoint(DSN),
    middleware=[RateLimit(max_calls=10, per_s=1.0)],
)
```

## 3. Distributed

Stateless workers pull jobs from a queue; all state external (Postgres/Redis).
A human-in-the-loop pause or a crash mid-run is recoverable because the resume
token points at the durable checkpoint — any worker can pick it up.

```toml
# spine.toml
[spine.backends]
checkpoint = "redis"

[spine.plugins.redis]
url = "${REDIS_URL}"
```

## Multi-tenancy

`tenant_id` flows through `State`; budgets and (with a namespacing store) isolation
are tenant-scoped. See [`TenantBudget`](guardrails.md#per-tenant-budgets).

## Observability in production

Add the [OTel middleware](../concepts/observability.md#opentelemetry) and point it
at your collector — spans carry token counts, cost, latency, model, and tool name,
so existing dashboards and your SIEM work unchanged.

## Cooperative shutdown

On `SIGTERM`, pass a `should_cancel` predicate to `run()`; the kernel finishes and
checkpoints the current step, then returns `cancelled` — the run resumes later
from exactly there.
