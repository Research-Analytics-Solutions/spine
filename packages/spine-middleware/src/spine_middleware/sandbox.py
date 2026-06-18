"""Sandbox middleware — run side-effecting / untrusted tools under resource limits.

Executes a *synchronous* tool in a forked child process with CPU, address-space,
and wall-clock limits, then kills it if it overruns. This is a **resource**
sandbox, not a security jail: it stops runaway CPU/memory and hangs, but for
genuinely untrusted code use a container/VM boundary.

POSIX only (needs ``os.fork``); on other platforms or for ``async`` tools it is a
no-op and the tool runs normally.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from typing import Any

import anyio

from spine_core.middleware import ToolContext


def _set_limits(cpu_s: int, mem_mb: int) -> None:
    try:
        import resource

        if cpu_s:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        if mem_mb:
            limit = mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except Exception:  # noqa: BLE001 - limits are best-effort
        pass


def _worker(func: Any, args: dict[str, Any], queue: Any, cpu_s: int, mem_mb: int) -> None:
    _set_limits(cpu_s, mem_mb)
    try:
        queue.put(("ok", func(**args)))
    except BaseException as exc:  # noqa: BLE001 - report any failure incl. limit kills
        queue.put(("err", repr(exc)))


class Sandbox:
    """Run sync tools in a resource-limited child process.

    Restrict to specific tools with ``tools=[...]`` (default: all sync tools).
    """

    def __init__(
        self,
        *,
        tools: list[str] | None = None,
        timeout_s: float = 5.0,
        max_cpu_s: int = 5,
        max_memory_mb: int = 512,
    ) -> None:
        self.tools = set(tools) if tools else None
        self.timeout_s = timeout_s
        self.max_cpu_s = max_cpu_s
        self.max_memory_mb = max_memory_mb

    def _applies(self, ctx: ToolContext) -> bool:
        if not hasattr(os, "fork"):  # non-POSIX: cannot sandbox
            return False
        tool = ctx.tool
        if tool is None or tool._is_async:  # async tools can't run in the fork worker
            return False
        return self.tools is None or ctx.call.name in self.tools

    async def before_tool(self, ctx: ToolContext) -> None:
        if not self._applies(ctx):
            return
        assert ctx.tool is not None
        validated = ctx.tool.validate(ctx.args)
        ctx.result = await anyio.to_thread.run_sync(
            self._run, ctx.tool.func, validated, ctx.call.name
        )
        ctx.skip = True

    def _run(self, func: Any, args: dict[str, Any], name: str) -> str:
        context = mp.get_context("fork")
        queue: Any = context.Queue()
        proc = context.Process(
            target=_worker, args=(func, args, queue, self.max_cpu_s, self.max_memory_mb)
        )
        proc.start()
        proc.join(self.timeout_s)
        if proc.is_alive():
            proc.terminate()
            proc.join()
            return f"Error: tool '{name}' exceeded the {self.timeout_s}s sandbox timeout"
        try:
            status, payload = queue.get_nowait()
        except Exception:  # noqa: BLE001 - empty queue means the child was killed
            return f"Error: tool '{name}' was killed by a sandbox resource limit"
        if status == "ok":
            return payload if isinstance(payload, str) else str(payload)
        return f"Error: sandboxed tool '{name}' failed: {payload}"
