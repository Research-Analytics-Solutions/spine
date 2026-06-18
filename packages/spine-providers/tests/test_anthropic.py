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


def test_multimodal_user_message_maps_to_anthropic_blocks() -> None:
    from spine_core import Message, image_part, text_part

    msg = Message.user_parts(
        [
            text_part("what is in this image?"),
            image_part(url="https://example.com/cat.png"),
            image_part(data="QUJD", media_type="image/jpeg"),
        ]
    )
    _, out = to_anthropic_messages([msg])
    content = out[0]["content"]
    assert content[0] == {"type": "text", "text": "what is in this image?"}
    assert content[1] == {
        "type": "image",
        "source": {"type": "url", "url": "https://example.com/cat.png"},
    }
    assert content[2]["source"]["type"] == "base64"
    assert content[2]["source"]["media_type"] == "image/jpeg"


async def test_anthropic_streaming_yields_deltas_then_final() -> None:
    from spine_providers.anthropic import AnthropicProvider

    class _FakeStream:
        async def __aenter__(self) -> _FakeStream:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        @property
        async def text_stream(self):  # type: ignore[no-untyped-def]
            for piece in ("hello ", "world"):
                yield piece

        async def get_final_message(self) -> Any:
            return SimpleNamespace(
                content=[_block(type="text", text="hello world")],
                usage=SimpleNamespace(input_tokens=3, output_tokens=2),
                stop_reason="end_turn",
            )

    class _Msgs:
        def stream(self, **params: Any) -> _FakeStream:
            return _FakeStream()

    client = SimpleNamespace(messages=_Msgs())
    provider = AnthropicProvider("claude-sonnet-4-6", client=client)
    chunks = [c async for c in provider.stream([Message.user("hi")])]
    deltas = [c.delta for c in chunks if c.delta]
    assert "".join(deltas) == "hello world"
    assert chunks[-1].response is not None
    assert chunks[-1].response.message.content == "hello world"
