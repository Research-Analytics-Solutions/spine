# spine-mcp

Mount a [Model Context Protocol](https://modelcontextprotocol.io) server's tools
into a Spine agent. Spine consumes MCP rather than inventing its own tool
protocol.

```python
from spine_core import Agent
from spine_mcp import MCPToolset

# streamable-HTTP server
async with MCPToolset(url="https://mcp.example.com/mcp") as mcp:
    tools = await mcp.load_tools()
    agent = Agent("anthropic:claude-sonnet-4-6", tools=tools)
    print((await agent.run("list my repos")).answer)

# or a local stdio server
async with MCPToolset(command="uvx", args=["mcp-server-git"]) as mcp:
    ...
```

Each MCP tool becomes a Spine `Tool` (name, description, JSON schema, callable).
The callable invokes the server over the live session, so use the toolset as an
async context manager to keep that session open for the duration of the run.
Pass `approve=True` to gate every server tool behind human-in-the-loop.
