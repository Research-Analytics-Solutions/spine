"""OpenAI provider adapter.

Implements the Spine ``Provider`` protocol over the official ``openai`` async SDK
(Chat Completions). Message/tool translation lives in pure functions so it is
testable without a network or API key.
"""

from __future__ import annotations

import json
from typing import Any

from spine_core.messages import Message, ModelResponse, Role, ToolCall, Usage
from spine_core.provider import register_provider

DEFAULT_MODEL = "gpt-4o"

# Approximate list price in USD per 1M tokens (input, output); matched by prefix.
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "o3-mini": (1.10, 4.40),
}


def _price_for(model: str) -> tuple[float, float] | None:
    if model in _PRICES:
        return _PRICES[model]
    for prefix, price in sorted(_PRICES.items(), key=lambda kv: -len(kv[0])):
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
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _parts_to_openai(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for part in parts:
        if part.get("type") == "image":
            if "url" in part:
                url = part["url"]
            else:
                media_type = part.get("media_type", "image/png")
                url = f"data:{media_type};base64,{part.get('data', '')}"
            blocks.append({"type": "image_url", "image_url": {"url": url}})
        else:
            blocks.append({"type": "text", "text": part.get("text", "")})
    return blocks


def to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Translate Spine messages to OpenAI Chat Completions format."""
    out: list[dict[str, Any]] = []
    for message in messages:
        if message.role is Role.ASSISTANT and message.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in message.tool_calls
                    ],
                }
            )
        elif message.role is Role.TOOL:
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content or "",
                }
            )
        elif message.role is Role.USER and message.parts:
            out.append({"role": "user", "content": _parts_to_openai(message.parts)})
        else:
            out.append({"role": message.role.value, "content": message.content or ""})
    return out


def to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def from_openai_response(resp: Any, model: str) -> ModelResponse:
    """Map an OpenAI Chat Completions response to a Spine ``ModelResponse``."""
    choice = (_attr(resp, "choices") or [None])[0]
    message = _attr(choice, "message")
    content = _attr(message, "content")

    tool_calls: list[ToolCall] = []
    for tc in _attr(message, "tool_calls", None) or []:
        function = _attr(tc, "function")
        raw_args = _attr(function, "arguments", "") or "{}"
        try:
            arguments = json.loads(raw_args)
        except (ValueError, TypeError):
            arguments = {}
        tool_calls.append(
            ToolCall(
                id=str(_attr(tc, "id", "")),
                name=str(_attr(function, "name", "")),
                arguments=arguments,
            )
        )

    usage_obj = _attr(resp, "usage")
    input_tokens = int(_attr(usage_obj, "prompt_tokens", 0) or 0)
    output_tokens = int(_attr(usage_obj, "completion_tokens", 0) or 0)

    return ModelResponse(
        message=Message.assistant(content=content, tool_calls=tool_calls),
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_cost(model, input_tokens, output_tokens),
        ),
        finish_reason=_attr(choice, "finish_reason"),
        raw=resp,
    )


class OpenAIProvider:
    """A Spine provider backed by OpenAI Chat Completions (lazy SDK client)."""

    def __init__(
        self,
        model: str | None = None,
        *,
        client: Any = None,
        api_key: str | None = None,
        **defaults: Any,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self._client = client
        self._api_key = api_key
        self._defaults = defaults

    def _ensure_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        client = self._ensure_client()
        params: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(messages),
            **self._defaults,
            **kwargs,
        }
        if tools:
            params["tools"] = to_openai_tools(tools)
        resp = await client.chat.completions.create(**params)
        return from_openai_response(resp, self.model)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        from spine_core.provider import StreamChunk

        client = self._ensure_client()
        params: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
            **self._defaults,
            **kwargs,
        }
        if tools:
            params["tools"] = to_openai_tools(tools)

        text_parts: list[str] = []
        fragments: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None
        usage_obj: Any = None

        stream = await client.chat.completions.create(**params)
        async for chunk in stream:
            usage_obj = _attr(chunk, "usage", usage_obj) or usage_obj
            choices = _attr(chunk, "choices") or []
            if not choices:
                continue
            delta = _attr(choices[0], "delta")
            content = _attr(delta, "content")
            if content:
                text_parts.append(content)
                yield StreamChunk(delta=content)
            for tc in _attr(delta, "tool_calls", None) or []:
                frag = fragments.setdefault(
                    int(_attr(tc, "index", 0) or 0), {"id": "", "name": "", "args": ""}
                )
                if _attr(tc, "id"):
                    frag["id"] = _attr(tc, "id")
                function = _attr(tc, "function")
                if _attr(function, "name"):
                    frag["name"] += _attr(function, "name")
                if _attr(function, "arguments"):
                    frag["args"] += _attr(function, "arguments")
            if _attr(choices[0], "finish_reason"):
                finish_reason = _attr(choices[0], "finish_reason")

        tool_calls: list[ToolCall] = []
        for frag in fragments.values():
            try:
                arguments = json.loads(frag["args"] or "{}")
            except (ValueError, TypeError):
                arguments = {}
            tool_calls.append(ToolCall(id=frag["id"], name=frag["name"], arguments=arguments))

        input_tokens = int(_attr(usage_obj, "prompt_tokens", 0) or 0)
        output_tokens = int(_attr(usage_obj, "completion_tokens", 0) or 0)
        response = ModelResponse(
            message=Message.assistant("".join(text_parts) or None, tool_calls=tool_calls),
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=_cost(self.model, input_tokens, output_tokens),
            ),
            finish_reason=finish_reason,
        )
        yield StreamChunk(response=response)


def _factory(model: str) -> OpenAIProvider:
    return OpenAIProvider(model)


def register() -> None:
    register_provider("openai", _factory)


register()
