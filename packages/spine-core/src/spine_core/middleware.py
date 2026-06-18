"""Middleware system — the onion the kernel composes around each step.

A middleware implements any subset of hook points. The kernel never *constructs*
behavior; it *invokes hooks*. This is how Retry, Guardrails, Compaction, OTel,
etc. are built without ever editing the kernel (Design Principle #2).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from spine_core.messages import Message, ModelResponse, ToolCall
from spine_core.state import State

if TYPE_CHECKING:
    from spine_core.tools import Tool


class ErrorAction(StrEnum):
    """What ``on_error`` instructs the kernel to do with a failed model call."""

    RETRY = "retry"
    SKIP = "skip"
    FAIL = "fail"
    FALLBACK = "fallback"


class StepContext:
    """Mutable per-step context shared across the model-call hooks.

    Middleware may rewrite ``messages``, swap the ``provider``, or read
    ``response`` after the model returns.
    """

    __slots__ = ("state", "messages", "tools", "response", "provider", "attempt", "extra")

    def __init__(
        self,
        state: State,
        messages: list[Message],
        tools: list[Tool],
        provider: Any = None,
    ) -> None:
        self.state = state
        self.messages = messages
        self.tools = tools
        self.provider = provider
        self.response: ModelResponse | None = None
        self.attempt = 0
        self.extra: dict[str, Any] = {}


class ToolContext:
    """Mutable per-tool-call context shared across the tool hooks."""

    __slots__ = ("state", "tool", "call", "args", "result", "error")

    def __init__(self, state: State, tool: Tool | None, call: ToolCall) -> None:
        self.state = state
        self.tool = tool
        self.call = call
        self.args: dict[str, Any] = dict(call.arguments)
        self.result: Any = None
        self.error: Exception | None = None


class Middleware:
    """Base class with no-op hooks; subclass and override what you need.

    Duck-typed objects implementing only some hooks work too — the chain calls a
    hook only if the middleware defines it.
    """

    async def before_model(self, ctx: StepContext) -> None: ...
    async def after_model(self, ctx: StepContext) -> None: ...
    async def before_tool(self, ctx: ToolContext) -> None: ...
    async def after_tool(self, ctx: ToolContext) -> None: ...
    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction | None: ...


class MiddlewareChain:
    """Composes middlewares into an explicit, inspectable onion.

    ``before_*`` hooks run outermost-first (list order); ``after_*`` hooks run
    innermost-first (reverse), so a wrapping middleware brackets the ones it
    encloses.
    """

    def __init__(self, middlewares: list[Any] | None = None) -> None:
        self.middlewares: list[Any] = list(middlewares or [])

    async def before_model(self, ctx: StepContext) -> None:
        for mw in self.middlewares:
            hook = getattr(mw, "before_model", None)
            if hook is not None:
                await hook(ctx)

    async def after_model(self, ctx: StepContext) -> None:
        for mw in reversed(self.middlewares):
            hook = getattr(mw, "after_model", None)
            if hook is not None:
                await hook(ctx)

    async def before_tool(self, ctx: ToolContext) -> None:
        for mw in self.middlewares:
            hook = getattr(mw, "before_tool", None)
            if hook is not None:
                await hook(ctx)

    async def after_tool(self, ctx: ToolContext) -> None:
        for mw in reversed(self.middlewares):
            hook = getattr(mw, "after_tool", None)
            if hook is not None:
                await hook(ctx)

    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction:
        """First middleware to return an action decides; default is FAIL."""
        for mw in self.middlewares:
            hook = getattr(mw, "on_error", None)
            if hook is None:
                continue
            action: ErrorAction | None = await hook(ctx, err)
            if action is not None:
                return action
        return ErrorAction.FAIL
