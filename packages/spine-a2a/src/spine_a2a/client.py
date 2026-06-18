"""A2A (agent-to-agent) client — call a remote agent and mount it as a tool.

Spine consumes the open A2A protocol rather than a proprietary handoff format.
A remote agent is reached over JSON-RPC (``message/send``); ``as_tool`` wraps it
so a local agent can delegate to it like any other tool.
"""

from __future__ import annotations

from typing import Any

import httpx

from spine_core import Tool, raw_tool

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"input": {"type": "string", "description": "Message for the remote agent."}},
    "required": ["input"],
}


def _extract_text(data: dict[str, Any]) -> str:
    """Pull text out of an A2A response, tolerant of Message/Task shapes."""
    if "error" in data and data["error"]:
        return f"A2A error: {data['error'].get('message', data['error'])}"
    result = data.get("result", data)

    def parts_text(parts: Any) -> str:
        out = [p.get("text", "") for p in (parts or []) if isinstance(p, dict)]
        return "\n".join(t for t in out if t)

    # direct message
    if isinstance(result, dict):
        text = parts_text(result.get("parts"))
        if text:
            return text
        # task with artifacts
        for artifact in result.get("artifacts") or []:
            text = parts_text(artifact.get("parts"))
            if text:
                return text
        # task status message
        status = result.get("status") or {}
        text = parts_text((status.get("message") or {}).get("parts"))
        if text:
            return text
    return ""


class A2AAgent:
    """A handle to a remote A2A agent reached over JSON-RPC."""

    def __init__(
        self,
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
        name: str | None = None,
        description: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.url = url
        self.name = name or "remote_agent"
        self.description = description or "Delegate a task to a remote A2A agent."
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def send(self, text: str) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
        }
        response = await self._ensure_client().post(self.url, json=payload)
        response.raise_for_status()
        return _extract_text(response.json())

    def as_tool(self, *, name: str | None = None, description: str | None = None) -> Tool:
        async def call(input: str) -> str:
            return await self.send(input)

        return raw_tool(name or self.name, description or self.description, _INPUT_SCHEMA, call)

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> A2AAgent:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
