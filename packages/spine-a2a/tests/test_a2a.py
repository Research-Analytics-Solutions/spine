"""A2A client: JSON-RPC send, text extraction shapes, tool wrapping, e2e."""

from __future__ import annotations

import json

import httpx

from spine_a2a import A2AAgent
from spine_a2a.client import _extract_text
from spine_core import Agent
from spine_core.testing import ScriptedProvider, calls, text


def _client(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_send_round_trips_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent = body["params"]["message"]["parts"][0]["text"]
        assert body["method"] == "message/send"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"role": "agent", "parts": [{"kind": "text", "text": f"echo: {sent}"}]},
            },
        )

    remote = A2AAgent("https://remote/a2a", client=_client(handler))
    assert await remote.send("hello") == "echo: hello"


def test_extract_text_from_task_artifacts() -> None:
    data = {"result": {"artifacts": [{"parts": [{"text": "from artifact"}]}]}}
    assert _extract_text(data) == "from artifact"


def test_extract_text_from_status_message() -> None:
    data = {"result": {"status": {"message": {"parts": [{"text": "from status"}]}}}}
    assert _extract_text(data) == "from status"


def test_extract_text_reports_error() -> None:
    data = {"error": {"code": -32000, "message": "boom"}}
    assert "boom" in _extract_text(data)


async def test_remote_agent_as_tool_end_to_end() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)["params"]["message"]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"parts": [{"text": f"remote saw: {sent}"}]},
            },
        )

    remote = A2AAgent("https://remote/a2a", client=_client(handler), name="researcher")
    provider = ScriptedProvider(
        calls(("researcher", {"input": "find otters"})),
        text("the researcher answered"),
    )
    agent = Agent(provider, tools=[remote.as_tool()])
    result = await agent.run("delegate")

    assert result.answer == "the researcher answered"
    tool_msg = next(m for m in result.state.messages if m.role.value == "tool")
    assert tool_msg.content == "remote saw: find otters"
