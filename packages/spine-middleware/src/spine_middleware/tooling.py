"""Tool-facing middlewares — per-tool timeout and output truncation."""

from __future__ import annotations

from spine_core.middleware import ToolContext


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else str(value)


class ToolTimeout:
    """Apply a wall-clock timeout to tool execution.

    Sets ``ctx.timeout_s`` in ``before_tool``; the kernel cancels the tool with
    ``anyio.fail_after`` and surfaces the timeout as a tool error to the model.
    Restrict to specific tools with ``tools=[...]``.
    """

    def __init__(self, timeout_s: float, *, tools: list[str] | None = None) -> None:
        self.timeout_s = timeout_s
        self.tools = set(tools) if tools else None

    async def before_tool(self, ctx: ToolContext) -> None:
        if self.tools is None or ctx.call.name in self.tools:
            ctx.timeout_s = self.timeout_s


class ToolOutputTruncation:
    """Cap huge tool outputs before they re-enter the context window."""

    def __init__(self, max_chars: int = 4000) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        self.max_chars = max_chars

    async def after_tool(self, ctx: ToolContext) -> None:
        if ctx.result is None:
            return
        text = _as_text(ctx.result)
        if len(text) > self.max_chars:
            removed = len(text) - self.max_chars
            ctx.result = f"{text[: self.max_chars]}…[truncated {removed} chars]"
