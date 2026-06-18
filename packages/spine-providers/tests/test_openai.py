"""OpenAI adapter: message/tool mapping, response parsing, registry, e2e."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from spine_core import Agent, Message, ToolCall, tool
from spine_providers.openai import (
    OpenAIProvider,
    from_openai_response,
    to_openai_messages,
    to_openai_tools,
)


class _FakeCompletions:
    def __init__(self, resp: Any) -> None:
        self._resp = resp
        self.captured: dict[str, Any] | None = None

    async def create(self, **params: Any) -> Any:
        self.captured = params
        return self._resp


class FakeOpenAI:
    def __init__(self, resp: Any) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(resp))


def test_messages_mapped_including_tool_calls_and_results() -> None:
    msgs = [
        Message.system("be terse"),
        Message.user("add 1 and 2"),
        Message.assistant(tool_calls=[ToolCall(id="c1", name="add", arguments={"a": 1, "b": 2})]),
        Message.tool("3", tool_call_id="c1", name="add"),
    ]
    out = to_openai_messages(msgs)
    assert out[0] == {"role": "system", "content": "be terse"}
    assert out[2]["role"] == "assistant"
    call = out[2]["tool_calls"][0]
    assert call["function"]["name"] == "add"
    assert json.loads(call["function"]["arguments"]) == {"a": 1, "b": 2}
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "3"}


def test_tool_schema_wrapped_as_function() -> None:
    @tool
    def search(query: str) -> str:
        """Search."""
        return query

    mapped = to_openai_tools([search.schema])
    assert mapped[0]["type"] == "function"
    assert mapped[0]["function"]["name"] == "search"
    assert mapped[0]["function"]["parameters"]["properties"]["query"]["type"] == "string"


def test_response_parsing_with_tool_call_and_cost() -> None:
    resp = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="here",
                    tool_calls=[
                        SimpleNamespace(
                            id="t1",
                            function=SimpleNamespace(name="add", arguments='{"a": 1, "b": 2}'),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=2000),
    )
    out = from_openai_response(resp, "gpt-4o")
    assert out.message.content == "here"
    assert out.message.tool_calls[0].arguments == {"a": 1, "b": 2}
    # 1000 * 2.5/M + 2000 * 10/M
    assert abs(out.usage.cost_usd - (0.0025 + 0.02)) < 1e-9
    assert out.finish_reason == "tool_calls"


def test_registry_resolves_openai_without_network() -> None:
    import spine_providers  # noqa: F401  (registers schemes)
    from spine_core.provider import resolve_provider

    provider = resolve_provider("openai:gpt-4o-mini")
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4o-mini"


async def test_end_to_end_run_with_fake_client() -> None:
    resp = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hi from gpt", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
    )
    provider = OpenAIProvider("gpt-4o", client=FakeOpenAI(resp))
    agent = Agent(provider, system="be helpful")
    result = await agent.run("hi")
    assert result.ok
    assert result.answer == "hi from gpt"
    captured = provider._client.chat.completions.captured
    assert captured["messages"][0] == {"role": "system", "content": "be helpful"}
    assert captured["model"] == "gpt-4o"
