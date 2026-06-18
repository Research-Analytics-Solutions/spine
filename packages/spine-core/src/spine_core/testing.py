"""In-repo test doubles — drive the kernel without a network.

``ScriptedProvider`` replays a queued list of responses, so the loop, guards,
tools, and HITL paths are tested deterministically. Real providers plug in via
the registry and satisfy the same one-method protocol.
"""

from __future__ import annotations

from typing import Any

from spine_core.messages import Message, ModelResponse, ToolCall, Usage


def text(
    content: str, *, input_tokens: int = 10, output_tokens: int = 5, cost_usd: float = 0.0
) -> ModelResponse:
    """A final assistant answer with no tool calls."""
    return ModelResponse(
        message=Message.assistant(content=content),
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd),
        finish_reason="stop",
    )


def calls(
    *tool_calls: tuple[str, dict[str, Any]],
    content: str | None = None,
    cost_usd: float = 0.0,
) -> ModelResponse:
    """An assistant turn requesting one or more tool calls."""
    parsed = [
        ToolCall(id=f"call_{i}", name=name, arguments=args)
        for i, (name, args) in enumerate(tool_calls)
    ]
    return ModelResponse(
        message=Message.assistant(content=content, tool_calls=parsed),
        usage=Usage(input_tokens=10, output_tokens=5, cost_usd=cost_usd),
        finish_reason="tool_calls",
    )


class ScriptedProvider:
    """Returns queued responses in order; raises if the script runs dry.

    Pass a single response to repeat it forever (useful for guard tests).
    """

    def __init__(self, *responses: ModelResponse, repeat: bool = False) -> None:
        self._responses = list(responses)
        self._repeat = repeat or len(responses) == 1
        self._index = 0
        self.calls: list[list[Message]] = []  # captured inputs, for assertions

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        self.calls.append(list(messages))
        if self._index >= len(self._responses):
            if self._repeat and self._responses:
                return self._responses[-1]
            raise AssertionError("ScriptedProvider exhausted: no more queued responses")
        response = self._responses[self._index]
        if not self._repeat:
            self._index += 1
        return response
