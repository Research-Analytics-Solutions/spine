# Quickstart

## The three-line agent

```python
from spine_core import Agent

agent = Agent("openai:gpt-4o-mini")
result = await agent.run("What is the capital of France?")
print(result.answer)
```

`Agent(...)` resolves the `scheme:model` string to a provider. `run()` returns a
[`Result`](reference/api.md) with the answer, the full trace, usage, and a
structured stop reason.

## Add a tool

A tool is a typed Python function. Arguments are validated against the derived
schema **before** the function runs.

```python
from spine_core import Agent, tool

@tool
async def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

agent = Agent("openai:gpt-4o-mini", tools=[add])
print((await agent.run("add 17 and 25")).answer)
```

## Guards: make runaway impossible

```python
from spine_core import Agent, Guards

agent = Agent(
    "openai:gpt-4o-mini",
    guards=Guards(max_steps=8, max_cost_usd=0.50, timeout_s=30),
)
```

Guards are checked **inside the kernel, every iteration**. The run stops with a
structured reason (`max_steps`, `max_cost`, `timeout`, …) — never an infinite loop.

## Stack middleware

Middleware is opt-in and explicitly ordered — the onion the kernel wraps around
each step.

```python
from spine_core import Agent, Guards
from spine_middleware import Retry, LoopGuard, CostTracking

agent = Agent(
    "openai:gpt-4o-mini",
    tools=[add],
    guards=Guards(max_steps=8, max_cost_usd=0.50),
    middleware=[Retry(max_attempts=3), LoopGuard(window=4), CostTracking(0.15, 0.60)],
)
```

## Run it without a network

Everything above is testable offline with the bundled scripted provider:

```python exec="1" source="above" result="text"
from spine_core import Agent
from spine_core.testing import ScriptedProvider, text

agent = Agent(ScriptedProvider(text("hello from spine")))
print(agent.run_sync("hi").answer)
```

## Next

- [The kernel](concepts/kernel.md) — how a run actually executes.
- [Models & any provider](guides/models.md) — OpenAI, Anthropic, Ollama, local, …
- [Middleware catalog](reference/middleware.md) — everything you can stack.
