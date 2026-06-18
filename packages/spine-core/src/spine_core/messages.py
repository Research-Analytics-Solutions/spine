"""Message primitives — the wire format the kernel and providers share.

Every model call consumes and produces these typed structures. Nothing in the
kernel constructs a prompt outside of an inspectable ``Message`` (Design
Principle #5: no hidden prompts).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    """Who authored a message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A model's request to invoke a tool. Arguments are raw (unvalidated)."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """A single conversational turn.

    ``content`` may be ``None`` on an assistant turn that only carries
    ``tool_calls``. ``tool_call_id`` links a ``TOOL`` result back to its request.
    """

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> Message:
        return cls(role=Role.ASSISTANT, content=content, tool_calls=tool_calls or [])

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str | None = None) -> Message:
        return cls(role=Role.TOOL, content=content, tool_call_id=tool_call_id, name=name)


class Usage(BaseModel):
    """Token + cost accounting for one or more model calls.

    ``cost_usd`` is set by the provider (or a cost-tracking middleware); the
    kernel's guards read it directly, so cost ceilings are enforced on real
    numbers rather than estimates.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )


class ModelResponse(BaseModel):
    """What a provider returns from ``complete``."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: Message
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    # Provider-native payload, kept for debugging; excluded from serialization.
    raw: Any = Field(default=None, exclude=True, repr=False)
