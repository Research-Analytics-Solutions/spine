# MCP tools

Spine consumes the [Model Context Protocol](https://modelcontextprotocol.io)
rather than inventing a tool protocol. `MCPToolset` connects to an MCP server,
lists its tools, and wraps each as a Spine tool.

```python
from spine_core import Agent
from spine_mcp import MCPToolset

# streamable-HTTP server
async with MCPToolset(url="https://mcp.example.com/mcp") as mcp:
    agent = Agent("openai:gpt-4o-mini", tools=await mcp.load_tools())
    print((await agent.run("list my repos")).answer)
```

Local stdio servers work too:

```python
async with MCPToolset(command="uvx", args=["mcp-server-git"]) as mcp:
    tools = await mcp.load_tools()
```

The toolset is an **async context manager** because the live session must stay
open for the duration of the run.

## Safety

Treat server tools as untrusted:

- `approve=True` gates every server tool behind [human approval](../concepts/hitl.md):

  ```python
  MCPToolset(url=..., approve=True)
  ```

- Stack [`PromptInjectionScreen`](guardrails.md) so tool output is treated as data,
  not instructions. Tool errors are surfaced to the model, never raised.
