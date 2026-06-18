# Guardrails & safety

Safety is built on hook points: tool output is treated as untrusted data, and
blocking guardrails stop the run cleanly (a `guardrail` stop reason, not a crash).

## PII redaction

Redacts email / SSN / credit-card / phone / IPv4 from tool output **before it
reaches the model or the trace**, and from the final answer:

```python
from spine_middleware import PIIRedaction

agent = Agent("openai:gpt-4o-mini", tools=tools, middleware=[PIIRedaction()])
```

## Prompt-injection screening

Treats tool output as untrusted — annotate with a caution banner (default) or
block on injection patterns:

```python
from spine_middleware import PromptInjectionScreen

# annotate (default) — wrap suspicious output so the model treats it as data
PromptInjectionScreen()
# or hard-block
PromptInjectionScreen(action="block")
```

## Content policy

Block the user input and/or the final answer on banned patterns or a custom
predicate:

```python
from spine_middleware import ContentPolicy

ContentPolicy(banned=["password", "ssn"])
ContentPolicy(validate=lambda text: len(text) < 2000)
```

## Reliability primitives

| Middleware | Protects against |
|---|---|
| `CircuitBreaker` | repeated provider failures — fail fast for a cooldown |
| `RateLimit` | exceeding a call budget (token bucket) |
| `Idempotency` | duplicate side effects on retries |
| `Sandbox` | runaway CPU/memory in a sync tool (subprocess + rlimits) |

## Per-tenant budgets

Enforce a cumulative cost/token ceiling per tenant across many runs:

```python
from spine_middleware import TenantBudget

budget = TenantBudget(max_cost_usd=10.0)
agent = Agent("openai:gpt-4o-mini", middleware=[budget], tenant_id="acme")
```

!!! warning "Sandbox scope"
    `Sandbox` is a **resource** sandbox (stops runaway CPU/memory/hangs), not a
    security jail. For genuinely untrusted code use a container or VM boundary.
