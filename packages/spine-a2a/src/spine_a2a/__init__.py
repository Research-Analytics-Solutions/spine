"""A2A (agent-to-agent) adapter for Spine.

```python
from spine_core import Agent
from spine_a2a import A2AAgent

async with A2AAgent("https://remote.example.com/a2a", name="researcher") as remote:
    agent = Agent("anthropic:claude-sonnet-4-6", tools=[remote.as_tool()])
    print((await agent.run("ask the researcher about otters")).answer)
```
"""

from __future__ import annotations

from spine_a2a.client import A2AAgent

__all__ = ["A2AAgent"]
