# spine-orchestration

Multi-agent patterns composed from plain agents — no new engine.

```python
from spine_core import Agent
from spine_orchestration import Sequential, supervisor, Handoff

# pipeline: each answer feeds the next
pipe = Sequential(researcher, writer, editor)
result = await pipe.run("write about otters")

# supervisor routes to workers (each becomes a tool)
boss = supervisor("anthropic:claude-sonnet-4-6", {"billing": billing_agent, "tech": tech_agent})
result = await boss.run("my invoice is wrong")

# handoff: agents transfer to a named peer mid-conversation
team = Handoff({"triage": triage, "specialist": specialist}, start="triage")
result = await team.run("escalate this")
print(team.path)  # ["triage", "specialist"]
```
