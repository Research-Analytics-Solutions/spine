"""MCP client adapter — mount a Model Context Protocol server's tools as Tool[].

Spine consumes MCP rather than inventing a tool protocol (Design Principle:
protocol-first). An :class:`MCPToolset` connects to a server (stdio command or
streamable-HTTP URL), lists its tools, and wraps each as a Spine
:func:`~spine_core.raw_tool` whose callable invokes the server. The live session
must stay open while the agent runs, so the toolset is an async context manager.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from spine_core import Tool, raw_tool

_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _result_to_text(result: Any) -> str:
    """Flatten an MCP tool result into message content the model can read."""
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(str(text))
    if parts:
        return "\n".join(parts)
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return json.dumps(structured, default=str)
    return ""


class MCPToolset:
    """Connects to one MCP server and exposes its tools to a Spine agent.

    Usage::

        async with MCPToolset(url="https://mcp.example.com/mcp") as mcp:
            agent = Agent("anthropic:claude-sonnet-4-6", tools=await mcp.load_tools())
            await agent.run("...")

    Pass ``session=`` to drive an existing/mock ``ClientSession`` (used in tests).
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        session: Any = None,
        approve: bool = False,
    ) -> None:
        if session is None and url is None and command is None:
            raise ValueError("MCPToolset needs a url, a command, or an explicit session")
        self.url = url
        self.command = command
        self.args = args or []
        self.env = env
        self.approve = approve
        self._session = session
        self._owns_session = session is None
        self._stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        from mcp import ClientSession

        self._stack = AsyncExitStack()
        if self.url is not None:
            from mcp.client.streamable_http import streamablehttp_client

            read, write, _ = await self._stack.enter_async_context(streamablehttp_client(self.url))
        else:
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(command=self.command or "", args=self.args, env=self.env)
            read, write = await self._stack.enter_async_context(stdio_client(params))

        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def load_tools(self) -> list[Tool]:
        """Connect (if needed), list the server's tools, and wrap them."""
        await self.connect()
        listing = await self._session.list_tools()
        tools: list[Tool] = []
        for spec in listing.tools:
            tools.append(
                raw_tool(
                    name=spec.name,
                    description=getattr(spec, "description", None) or "",
                    parameters=getattr(spec, "inputSchema", None) or dict(_EMPTY_SCHEMA),
                    func=self._make_caller(spec.name),
                    approve=self.approve,
                )
            )
        return tools

    def _make_caller(self, name: str) -> Any:
        async def call(**kwargs: Any) -> str:
            result = await self._session.call_tool(name, kwargs)
            if getattr(result, "isError", False):
                return f"MCP tool '{name}' error: {_result_to_text(result)}"
            return _result_to_text(result)

        return call

    async def aclose(self) -> None:
        if self._stack is not None and self._owns_session:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def __aenter__(self) -> MCPToolset:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
