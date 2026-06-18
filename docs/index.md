---
template: home.html
hide:
  - navigation
  - toc
---

## Three guarantees

<div class="grid cards" markdown>

-   :material-eye-outline:{ .lg .middle } **No hidden prompts**

    ---

    Every model call consumes inspectable, typed `Message` objects. No prompt is
    ever constructed outside your view.

-   :material-shield-check-outline:{ .lg .middle } **No runaway loops**

    ---

    [Guards](concepts/guards.md) are enforced inside the kernel, every iteration —
    not bolted on. Step, cost, token, wall-clock, and delegation ceilings are
    structural.

-   :material-history:{ .lg .middle } **Deterministic replay**

    ---

    Every step emits a trace event; any run can be
    [recorded and replayed](concepts/observability.md) step-for-step without
    calling the provider or any tool.

</div>

## What's in the box

| Plane | Ships with |
|---|---|
| **Kernel** | step loop, explicit serializable state, guards, tracer, HITL interrupt/resume, parallel tools, cancellation, sub-agents |
| **Middleware** | retry, fallback, loop guard, structured output, compaction, cost tracking, caching, **guardrails** (PII/injection/policy), circuit breaker, idempotency, rate limit, deterministic replay, memory recall, tenant budgets, tool timeout/truncation/sandbox |
| **Backends** | checkpoints (in-memory, SQLite, Redis, Postgres); memory (vector, buffer, pgvector) with pluggable embedders |
| **Providers** | OpenAI, Anthropic — and any OpenAI-compatible endpoint (Ollama, vLLM, Groq, …). See [Models](guides/models.md) |
| **Adapters** | MCP (tools), A2A (remote agents), OpenTelemetry (spans) |
| **Tooling** | CLI (`init`/`run`/`chat`/`dev`/`trace`/`eval`/`doctor`/`plugin`), eval harness, orchestration patterns |

## Why Spine

The integration layer that made monolithic frameworks valuable has been
commoditized by open standards (MCP for tools, A2A for agents). The durable value
sits in the **reliability runtime** — the execution loop, guards, durable state,
and observability that decide whether an agent survives production. Spine owns that
core and lets the standards do the integration.

[Get started :material-arrow-right:](quickstart.md){ .md-button .md-button--primary }
[Read the architecture](architecture.md){ .md-button }
