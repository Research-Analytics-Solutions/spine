# Deep dive: MCP

A complete walkthrough of mounting [Model Context
Protocol](https://modelcontextprotocol.io) servers with `spine-mcp`.

## How it works

`MCPToolset` opens a session to one MCP server, calls `list_tools`, and wraps each
returned tool as a Spine [`raw_tool`](../concepts/tools.md#from-a-raw-schema) whose
callable invokes the server via `call_tool`. Because the live session must stay
open while the agent runs, the toolset is an **async context manager**.

```python
from spine_core import Agent
from spine_mcp import MCPToolset

async with MCPToolset(url="https://mcp.example.com/mcp") as mcp:
    tools = await mcp.load_tools()
    agent = Agent("openai:gpt-4o-mini", tools=tools)
    print((await agent.run("list my open issues")).answer)
```

## Connection types

=== "Streamable HTTP"

    ```python
    MCPToolset(url="https://mcp.example.com/mcp")
    ```

=== "Local stdio server"

    ```python
    MCPToolset(command="uvx", args=["mcp-server-git", "--repository", "."])
    # optional environment for the child:
    MCPToolset(command="node", args=["server.js"], env={"TOKEN": "..."})
    ```

The constructor needs **one** of `url`, `command`, or an explicit `session` (used
for testing). It raises `ValueError` otherwise.

## Combining MCP tools with your own

`load_tools()` returns a plain `list[Tool]` — mix them with local `@tool`
functions:

```python
from spine_core import tool

@tool
async def notify(channel: str, text: str) -> str:
    """Post to a channel."""
    ...

async with MCPToolset(command="uvx", args=["mcp-server-git"]) as git:
    agent = Agent("openai:gpt-4o-mini", tools=[*await git.load_tools(), notify])
```

## Treat server tools as untrusted

MCP tools come from outside your codebase. Harden them:

```python
from spine_middleware import PromptInjectionScreen, ToolOutputTruncation

async with MCPToolset(url=URL, approve=True) as mcp:          # gate every tool behind HITL
    agent = Agent(
        "openai:gpt-4o-mini",
        tools=await mcp.load_tools(),
        middleware=[
            PromptInjectionScreen(),         # output is data, not instructions
            ToolOutputTruncation(max_chars=4000),
        ],
    )
```

- `approve=True` makes every server tool a [human-in-the-loop](../concepts/hitl.md)
  gate.
- A tool error from the server is **surfaced to the model** as an error string,
  never raised — the run keeps going.

## Multiple servers

Open several toolsets and concatenate their tools:

```python
async with MCPToolset(url=GITHUB) as gh, MCPToolset(command="uvx", args=["mcp-server-fs"]) as fs:
    agent = Agent("openai:gpt-4o-mini", tools=[*await gh.load_tools(), *await fs.load_tools()])
```

## Testing without a server

Inject a fake session implementing `list_tools` / `call_tool`:

```python
toolset = MCPToolset(session=my_fake_session)
tools = await toolset.load_tools()
```

This is exactly how `spine-mcp`'s own tests run — no network required.
