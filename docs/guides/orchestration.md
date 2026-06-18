# Multi-agent orchestration

Multi-agent patterns are thin compositions over plain agents — not a new engine.
From `spine-orchestration`:

## Sequential pipeline

Each agent's answer becomes the next agent's input.

```python
from spine_orchestration import Sequential

pipe = Sequential(researcher, writer, editor)
result = await pipe.run("write a post about otters")
```

## Supervisor

A supervisor agent routes to workers — each worker becomes a tool via
`agent.as_tool()`.

```python
from spine_orchestration import supervisor

boss = supervisor("openai:gpt-4o-mini", {"billing": billing_agent, "tech": tech_agent})
result = await boss.run("my invoice is wrong")
```

## Handoff

Agents transfer the conversation to a named peer via injected `transfer_to_<peer>`
tools. Bounded by `max_handoffs`; the path is recorded.

```python
from spine_orchestration import Handoff

team = Handoff({"triage": triage, "specialist": specialist}, start="triage")
result = await team.run("escalate this")
print(team.path)   # ["triage", "specialist"]
```

## Sub-agents and remote agents

- `agent.as_tool()` — any agent as a tool, with delegation-depth cycle bounding.
- `A2AAgent(url).as_tool()` — a **remote** agent over the A2A protocol:

  ```python
  from spine_a2a import A2AAgent

  async with A2AAgent("https://remote/a2a", name="researcher") as remote:
      agent = Agent("openai:gpt-4o-mini", tools=[remote.as_tool()])
  ```
