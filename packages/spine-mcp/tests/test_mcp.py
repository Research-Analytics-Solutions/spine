"""MCP toolset: tool discovery, wrapping, invocation, error flattening."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from spine_core import Agent
from spine_core.testing import ScriptedProvider, calls, text
from spine_mcp import MCPToolset


class FakeSession:
    """Stands in for an mcp ClientSession."""

    def __init__(self, *, error: bool = False) -> None:
        self.error = error
        self.invocations: list[tuple[str, dict[str, Any]]] = []

    async def initialize(self) -> None:  # pragma: no cover - trivial
        pass

    async def list_tools(self) -> Any:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="search",
                    description="Search the web",
                    inputSchema={
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                )
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.invocations.append((name, arguments))
        if self.error:
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="boom")], isError=True
            )
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=f"results for {arguments['q']}")],
            isError=False,
        )


async def test_load_tools_wraps_server_tools() -> None:
    toolset = MCPToolset(session=FakeSession())
    tools = await toolset.load_tools()
    assert len(tools) == 1
    assert tools[0].name == "search"
    assert tools[0].description == "Search the web"
    assert tools[0].parameters["properties"]["q"]["type"] == "string"


async def test_agent_calls_mcp_tool_end_to_end() -> None:
    session = FakeSession()
    toolset = MCPToolset(session=session)
    tools = await toolset.load_tools()

    provider = ScriptedProvider(calls(("search", {"q": "spine"})), text("done"))
    agent = Agent(provider, tools=tools)
    result = await agent.run("find spine")

    assert result.answer == "done"
    assert session.invocations == [("search", {"q": "spine"})]
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert tool_msg.content == "results for spine"


async def test_mcp_tool_error_is_surfaced_not_raised() -> None:
    toolset = MCPToolset(session=FakeSession(error=True))
    tools = await toolset.load_tools()
    provider = ScriptedProvider(calls(("search", {"q": "x"})), text("ok"))
    agent = Agent(provider, tools=tools)
    result = await agent.run("go")

    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert "error" in (tool_msg.content or "").lower()


def test_requires_a_connection_target() -> None:
    import pytest

    with pytest.raises(ValueError):
        MCPToolset()
