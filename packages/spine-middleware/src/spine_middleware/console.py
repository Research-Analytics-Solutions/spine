"""ConsoleLogger — opt-in pretty terminal logging of a run.

The kernel never writes to the terminal; trace events are data on
``Result.trace``. Add this middleware to ``middleware=[...]`` when you *want* a
live, human-readable log of each step. Uses Rich if installed, plain ``print``
otherwise. Writes to stderr so it doesn't interfere with stdout/piped output.

It is **opt-in**: nothing prints unless you add it. The kernel's default behavior
is unchanged.
"""

from __future__ import annotations

import re
import time
from typing import Any

from spine_core.middleware import ErrorAction, StepContext, ToolContext
from spine_core.result import Result
from spine_core.state import State

_MARKUP = re.compile(r"\[/?[^\]]*\]")


def _fmt_args(args: dict[str, Any], limit: int = 60) -> str:
    s = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return s if len(s) <= limit else s[:limit] + "…"


class ConsoleLogger:
    """Print a readable, aligned log line for each step, tool call, and result.

    Parameters: ``prefix`` (the label shown per line, default ``"spine"``),
    ``timestamp`` (prepend HH:MM:SS), and ``console`` (inject a Rich Console).
    """

    def __init__(
        self, *, prefix: str = "spine", timestamp: bool = True, console: Any = None
    ) -> None:
        self.prefix = prefix
        self.timestamp = timestamp
        self._console = console
        self._resolved = console is not None

    def _log(self, symbol: str, label: str, msg: str, color: str) -> None:
        if not self._resolved:
            try:
                from rich.console import Console

                self._console = Console(stderr=True)
            except Exception:  # noqa: BLE001 - Rich is optional
                self._console = None
            self._resolved = True

        ts = time.strftime("%H:%M:%S") if self.timestamp else ""
        if self._console is None:
            line = f"{ts} {self.prefix} {symbol} {label:<6} {_MARKUP.sub('', msg)}".strip()
            print(line)
        else:
            t = f"[dim]{ts}[/] " if ts else ""
            self._console.print(
                f"{t}[blue]{self.prefix}[/] [{color}]{symbol}[/] [bold]{label:<6}[/] {msg}"
            )

    async def on_run_start(self, state: State) -> None:
        self._log("▶", "run", f"[dim]{state.session_id[:8]}[/]", "magenta")

    async def before_model(self, ctx: StepContext) -> None:
        self._log("→", "model", f"step {ctx.state.step} · {len(ctx.messages)} msg", "cyan")

    async def after_model(self, ctx: StepContext) -> None:
        r = ctx.response
        if r is None:
            return
        calls = ", ".join(c.name for c in r.message.tool_calls)
        extra = f" · wants: {calls}" if calls else ""
        self._log(
            "←", "model", f"{r.usage.total_tokens} tok · ${r.usage.cost_usd:.5f}{extra}", "cyan"
        )

    async def before_tool(self, ctx: ToolContext) -> None:
        self._log("⚙", "tool", f"{ctx.call.name}([dim]{_fmt_args(ctx.args)}[/])", "yellow")

    async def after_tool(self, ctx: ToolContext) -> None:
        result = str(ctx.result)
        if len(result) > 70:
            result = result[:70] + "…"
        if ctx.error is not None:
            self._log("✗", "tool", f"{ctx.call.name} → [red]{result}[/]", "red")
        else:
            self._log("✓", "tool", f"{ctx.call.name} → {result}", "green")

    async def on_error(self, ctx: StepContext, err: Exception) -> ErrorAction | None:
        self._log("✗", "error", f"{type(err).__name__}: {err}", "red")
        return None

    async def on_run_end(self, state: State, result: Result) -> None:
        reason = result.stopped_reason.value
        color = "red" if reason in ("error", "guardrail", "loop") else "green"
        msg = f"[bold]{reason}[/] · {state.step} steps · ${state.usage.cost_usd:.5f}"
        self._log("■", "done", msg, color)
