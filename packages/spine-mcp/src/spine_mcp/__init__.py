"""MCP (Model Context Protocol) client adapter for Spine.

```python
from spine_core import Agent
from spine_mcp import MCPToolset

async with MCPToolset(url="https://mcp.example.com/mcp") as mcp:
    agent = Agent("anthropic:claude-sonnet-4-6", tools=await mcp.load_tools())
    print((await agent.run("list my repos")).answer)
```
"""

from __future__ import annotations

from spine_mcp.toolset import MCPToolset

__all__ = ["MCPToolset"]
