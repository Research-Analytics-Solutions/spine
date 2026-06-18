"""Anthropic adapter: message/tool mapping, response parsing, registry, e2e."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from spine_core import Agent, Message, ToolCall, tool
from spine_providers.anthropic import (
    AnthropicProvider,
    from_anthropic_response,
    to_anthropic_messages,
    to_anthropic_tools,
)


def _block(**kw: Any) -> SimpleNamespace:
    return SimpleNamespace(**kw)


class _FakeMessages:
    def __init__(self, resp: Any) -> None:
        self._resp = resp
        self.captured: dict[str, Any] | None = None

    async def create(self, **params: Any) -> Any:
        self.captured = params
        return self._resp


class FakeAnthropic:
    def __init__(self, resp: Any) -> None:
        self.messages = _FakeMessages(resp)


def test_system_messages_lifted_out() -> None:
    msgs = [
        Message.system("be terse"),
        Message.system("be kind"),
        Message.user("hi"),
    ]
    system, out = to_anthropic_messages(msgs)
    assert system == "be terse\n\nbe kind"
    assert out == [{"role": "user", "content": "hi"}]


def test_assistant_tool_use_and_tool_result_merge() -> None:
    msgs = [
        Message.user("add 1 and 2"),
        Message.assistant(tool_calls=[ToolCall(id="c1", name="add", arguments={"a": 1, "b": 2})]),
        Message.tool("3", tool_call_id="c1", name="add"),
        Message.tool("ignored", tool_call_id="c2", name="add"),
    ]
    _, out = to_anthropic_messages(msgs)
    assert out[1]["role"] == "assistant"
    assert out[1]["content"][0] == {
        "type": "tool_use",
        "id": "c1",
        "name": "add",
        "input": {"a": 1, "b": 2},
    }
    # both tool results collapse into one user turn
    assert out[2]["role"] == "user"
    assert len(out[2]["content"]) == 2
    assert out[2]["content"][0]["type"] == "tool_result"


def test_tool_schema_mapped_to_input_schema() -> None:
    @tool
    def search(query: str) -> str:
        """Search."""
        return query

    mapped = to_anthropic_tools([search.schema])
    assert mapped[0]["name"] == "search"
    assert "input_schema" in mapped[0]
    assert mapped[0]["input_schema"]["properties"]["query"]["type"] == "string"


def test_response_parsing_text_tools_usage_cost() -> None:
    resp = SimpleNamespace(
        content=[
            _block(type="text", text="here you go"),
            _block(type="tool_use", id="t1", name="add", input={"a": 1, "b": 2}),
        ],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=2000),
        stop_reason="tool_use",
    )
    out = from_anthropic_response(resp, "claude-sonnet-4-6")
    assert out.message.content == "here you go"
    assert out.message.tool_calls[0].name == "add"
    assert out.message.tool_calls[0].arguments == {"a": 1, "b": 2}
    assert out.usage.input_tokens == 1000
    # 1000 in * $3/Mtok + 2000 out * $15/Mtok = 0.003 + 0.030
    assert abs(out.usage.cost_usd - 0.033) < 1e-9
    assert out.finish_reason == "tool_use"


def test_registry_resolves_scheme_without_network() -> None:
    import spine_providers  # noqa: F401  (import registers the scheme)
    from spine_core.provider import resolve_provider

    provider = resolve_provider("anthropic:claude-sonnet-4-6")
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-4-6"


async def test_end_to_end_run_with_fake_client() -> None:
    resp = SimpleNamespace(
        content=[_block(type="text", text="hello from claude")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=4),
        stop_reason="end_turn",
    )
    provider = AnthropicProvider("claude-sonnet-4-6", client=FakeAnthropic(resp))
    agent = Agent(provider, system="be helpful")
    result = await agent.run("hi")
    assert result.ok
    assert result.answer == "hello from claude"
    # system prompt was lifted to the top-level param, not the message list
    captured = provider._client.messages.captured
    assert captured["system"] == "be helpful"
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["max_tokens"] == 1024
