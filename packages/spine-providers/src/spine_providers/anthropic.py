"""Anthropic provider adapter.

Implements the Spine ``Provider`` protocol over the official ``anthropic`` async
SDK. The translation between Spine's typed ``Message`` wire format and the
Anthropic Messages API is split into pure functions so it is testable without a
network or API key.
"""

from __future__ import annotations

from typing import Any

from spine_core.messages import Message, ModelResponse, Role, ToolCall, Usage
from spine_core.provider import register_provider

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024

# Approximate list price in USD per 1M tokens (input, output). Authoritative
# cost tracking belongs in the cost middleware; this gives cost guards a usable
# default out of the box. Matched by exact id, then by prefix.
_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (1.0, 5.0),
}


def _price_for(model: str) -> tuple[float, float] | None:
    if model in _PRICES:
        return _PRICES[model]
    for prefix, price in _PRICES.items():
        if model.startswith(prefix):
            return price
    return None


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = _price_for(model)
    if price is None:
        return 0.0
    in_rate, out_rate = price
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read an attribute or dict key — tolerant of SDK objects and plain dicts."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _parts_to_anthropic(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for part in parts:
        if part.get("type") == "image":
            if "url" in part:
                source = {"type": "url", "url": part["url"]}
            else:
                source = {
                    "type": "base64",
                    "media_type": part.get("media_type", "image/png"),
                    "data": part.get("data", ""),
                }
            blocks.append({"type": "image", "source": source})
        else:
            blocks.append({"type": "text", "text": part.get("text", "")})
    return blocks


def to_anthropic_messages(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
    """Split Spine messages into (system prompt, Anthropic message list).

    ``system`` is a top-level Anthropic param; consecutive tool results are
    merged into a single ``user`` turn of ``tool_result`` blocks, as the API
    expects.
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for message in messages:
        if message.role == Role.SYSTEM:
            if message.content:
                system_parts.append(message.content)
        elif message.role == Role.USER:
            if message.parts:
                out.append({"role": "user", "content": _parts_to_anthropic(message.parts)})
            else:
                out.append({"role": "user", "content": message.content or ""})
        elif message.role == Role.ASSISTANT:
            if message.tool_calls:
                blocks: list[dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                    for tc in message.tool_calls
                )
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": "assistant", "content": message.content or ""})
        elif message.role == Role.TOOL:
            block = {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": message.content or "",
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})

    system = "\n\n".join(system_parts) if system_parts else None
    return system, out


def to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("parameters") or {"type": "object", "properties": {}},
        }
        for tool in tools
    ]


def from_anthropic_response(resp: Any, model: str) -> ModelResponse:
    """Map an Anthropic Messages API response to a Spine ``ModelResponse``."""
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in _attr(resp, "content", []) or []:
        btype = _attr(block, "type")
        if btype == "text":
            text_parts.append(str(_attr(block, "text", "")))
        elif btype == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=str(_attr(block, "id", "")),
                    name=str(_attr(block, "name", "")),
                    arguments=dict(_attr(block, "input", {}) or {}),
                )
            )

    usage_obj = _attr(resp, "usage")
    input_tokens = int(_attr(usage_obj, "input_tokens", 0) or 0)
    output_tokens = int(_attr(usage_obj, "output_tokens", 0) or 0)

    message = Message.assistant(
        content="\n".join(text_parts) if text_parts else None,
        tool_calls=tool_calls,
    )
    return ModelResponse(
        message=message,
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_cost(model, input_tokens, output_tokens),
        ),
        finish_reason=_attr(resp, "stop_reason"),
        raw=resp,
    )


class AnthropicProvider:
    """A Spine provider backed by Anthropic's Messages API.

    The SDK client is created lazily on first call, so constructing the provider
    (e.g. via the registry) never requires an API key or a network round-trip.
    Inject ``client`` to test without the SDK.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        client: Any = None,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **defaults: Any,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._client = client
        self._api_key = api_key
        self._defaults = defaults

    def _ensure_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        client = self._ensure_client()
        system, anth_messages = to_anthropic_messages(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anth_messages,
            **self._defaults,
            **kwargs,
        }
        if system is not None:
            params["system"] = system
        if tools:
            params["tools"] = to_anthropic_tools(tools)
        resp = await client.messages.create(**params)
        return from_anthropic_response(resp, self.model)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        from spine_core.provider import StreamChunk

        client = self._ensure_client()
        system, anth_messages = to_anthropic_messages(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anth_messages,
            **self._defaults,
            **kwargs,
        }
        if system is not None:
            params["system"] = system
        if tools:
            params["tools"] = to_anthropic_tools(tools)

        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield StreamChunk(delta=text)
            final = await stream.get_final_message()
        yield StreamChunk(response=from_anthropic_response(final, self.model))


def _factory(model: str) -> AnthropicProvider:
    return AnthropicProvider(model)


def register() -> None:
    """Register the ``anthropic:`` scheme with the Spine provider registry."""
    register_provider("anthropic", _factory)


# Self-register on module import (idempotent). Importing this module — directly,
# via ``import spine_providers``, or by loading the ``spine.plugins`` entry point
# — makes ``Agent("anthropic:...")`` resolvable. The import is cheap: the heavy
# anthropic SDK is only imported lazily on the first ``complete`` call.
register()
