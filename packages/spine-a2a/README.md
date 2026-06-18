# spine-a2a

Call a remote agent over the open [A2A](https://a2a-protocol.org) protocol and
mount it as a tool in a local Spine agent.

```python
from spine_core import Agent
from spine_a2a import A2AAgent

async with A2AAgent("https://remote.example.com/a2a", name="researcher") as remote:
    agent = Agent("anthropic:claude-sonnet-4-6", tools=[remote.as_tool()])
    print((await agent.run("ask the researcher about otters")).answer)
```

Messages go out as JSON-RPC `message/send`; the reply text is extracted from a
Message, Task artifacts, or task status (whichever the server returns). Use the
async context manager so the HTTP client is closed.
