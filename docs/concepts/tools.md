# Tools

A tool is `name + description + JSON schema + callable`. Arguments are validated
against the schema **before** the callable runs.

## From a typed function

```python
from spine_core import tool

@tool
async def search(query: str, limit: int = 10) -> str:
    """Search the web."""
    ...
```

`@tool` derives the JSON schema from the signature and type hints, and the
description from the docstring. Sync functions work too (they run off the event
loop):

```python
@tool
def square(x: int) -> int:
    """Square a number."""
    return x * x
```

## From a raw schema

For adapters whose tools aren't Python functions (MCP, A2A), build a tool from a
ready-made schema with `raw_tool`:

```python
from spine_core import raw_tool

async def call(**kwargs) -> str:
    return await remote_invoke(kwargs)

t = raw_tool(
    "lookup",
    "Look something up.",
    {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
    call,
)
```

## Human approval (HITL)

One flag gates a tool behind human approval — see [Human-in-the-loop](hitl.md):

```python
@tool(approve=True)
async def transfer_funds(amount: int, to: str) -> str:
    """Move money — requires approval."""
    ...
```

## Tools from anywhere

- **MCP servers** — [`MCPToolset`](../guides/mcp.md) mounts a whole server's tools.
- **Other agents** — `agent.as_tool()` makes a sub-agent callable.
- **Remote agents** — [`A2AAgent.as_tool()`](../guides/orchestration.md) over A2A.

## Hardening tool execution

Stack middleware to make tools production-safe:

- `ToolTimeout` — per-tool wall-clock limit.
- `ToolOutputTruncation` — cap huge outputs before they re-enter the context.
- `Idempotency` — run a side-effecting tool once per `(tool, args)`.
- `Sandbox` — run a sync tool in a resource-limited subprocess.
- `PromptInjectionScreen` — treat tool output as untrusted data.
