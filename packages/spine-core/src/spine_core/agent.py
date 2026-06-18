"""The kernel — the load-bearing ~loop everything else plugs into.

The kernel never *constructs* behavior; it loads state, checks guards, invokes
middleware hooks, calls the provider, runs validated tools, emits a trace event
per transition, and checkpoints. Guards run every iteration in here, which is
what makes runaway loops structurally impossible. HITL pauses are durable: a
paused run returns a resume token backed by a checkpoint and can outlive the
process.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import anyio
from pydantic import BaseModel

from spine_core.checkpoint import CheckpointStore, InMemoryCheckpointStore
from spine_core.control import StopRun
from spine_core.guards import Guards
from spine_core.interrupt import Interrupt
from spine_core.messages import Message, ToolCall
from spine_core.middleware import ErrorAction, MiddlewareChain, StepContext, ToolContext
from spine_core.provider import Provider, resolve_provider
from spine_core.result import Result, StopReason
from spine_core.state import PendingApproval, RunStatus, State
from spine_core.tools import Tool, raw_tool
from spine_core.trace import EventType, Tracer

# Tracks sub-agent delegation depth across as_tool() calls for cycle bounding.
_DELEGATION_DEPTH: contextvars.ContextVar[int] = contextvars.ContextVar(
    "spine_delegation_depth", default=0
)

# Hard safety net: even if a middleware keeps asking to retry/fallback forever,
# the kernel refuses to call the provider more than this many times per step.
_MAX_PROVIDER_ATTEMPTS = 100


def _new_session_id() -> str:
    return uuid.uuid4().hex


def _stringify(value: Any) -> str:
    """Render a tool result into message content the model can read."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    try:
        return json.dumps(value, default=str)
    except TypeError:
        return str(value)


def _is_approved(decision: Any) -> bool:
    if isinstance(decision, bool):
        return decision
    if isinstance(decision, str):
        return decision.strip().lower() in {"approve", "approved", "yes", "y", "true", "ok"}
    return bool(decision)


class _Pause(Exception):  # noqa: N818 - control-flow signal, not an error
    """Internal signal: a tool call must hand control back to a human."""

    def __init__(self, call: ToolCall, mode: str, payload: Any, remaining: list[ToolCall]) -> None:
        self.call = call
        self.mode = mode
        self.payload = payload
        self.remaining = remaining


class Agent:
    """A configured agent: a provider, tools, guards, and a middleware onion."""

    def __init__(
        self,
        model: str | Provider,
        *,
        tools: list[Tool] | None = None,
        guards: Guards | None = None,
        middleware: list[Any] | None = None,
        checkpoint: CheckpointStore | None = None,
        provider: Provider | None = None,
        system: str | None = None,
        name: str | None = None,
        parallel_tools: bool = False,
    ) -> None:
        self.provider: Provider = provider or resolve_provider(model)
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.guards = guards or Guards()
        self.chain = MiddlewareChain(middleware)
        self.checkpoint: CheckpointStore = checkpoint or InMemoryCheckpointStore()
        self.system = system
        self.name = name
        self.parallel_tools = parallel_tools
        self.last_result: Result | None = None

    # -- public API ---------------------------------------------------------

    async def run(
        self,
        input: str,
        *,
        session_id: str | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Result:
        state = await self._start(input, session_id)
        await self.chain.on_run_start(state)
        result = await self._loop(state, Tracer(), time.monotonic(), should_cancel)
        await self.chain.on_run_end(state, result)
        return result

    def as_tool(
        self, *, name: str | None = None, description: str | None = None, max_depth: int = 8
    ) -> Tool:
        """Expose this agent as a tool another agent can call (sub-agent).

        Delegation depth is tracked across calls so an A->B->A cycle is bounded.
        """
        tool_name = name or self.name or "subagent"

        async def call(input: str) -> str:
            depth = _DELEGATION_DEPTH.get()
            if depth >= max_depth:
                return f"Error: max delegation depth ({max_depth}) exceeded"
            token = _DELEGATION_DEPTH.set(depth + 1)
            try:
                result = await self.run(input)
            finally:
                _DELEGATION_DEPTH.reset(token)
            return result.answer or f"[sub-agent stopped: {result.stopped_reason.value}]"

        schema = {
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Task for the sub-agent."}},
            "required": ["input"],
        }
        return raw_tool(
            tool_name, description or f"Delegate a task to the {tool_name} agent.", schema, call
        )

    async def stream(self, input: str, *, session_id: str | None = None) -> AsyncIterator[Any]:
        """Yield trace events live as the run executes; final ``Result`` lands
        on ``self.last_result``."""
        state = await self._start(input, session_id)
        queue: asyncio.Queue[Any] = asyncio.Queue()
        sentinel = object()
        tracer = Tracer(listener=queue.put_nowait)
        started = time.monotonic()
        await self.chain.on_run_start(state)

        async def runner() -> Result:
            try:
                result = await self._loop(state, tracer, started)
                await self.chain.on_run_end(state, result)
                return result
            finally:
                queue.put_nowait(sentinel)

        task = asyncio.create_task(runner())
        while True:
            event = await queue.get()
            if event is sentinel:
                break
            yield event
        self.last_result = await task

    async def resume(self, token: str, decision: Any = "approve") -> Result:
        """Continue a paused (HITL) run with a human decision.

        ``token`` is the run's session id (see :meth:`_pause`). Because it maps
        directly to a durable checkpoint, a pause can outlive the process: a
        fresh ``Agent`` sharing the same checkpoint store resumes it.
        """
        from spine_core.errors import ResumeError

        state = await self.checkpoint.get(token)
        if state is None or state.pending is None:
            raise ResumeError(f"no resumable run for token {token!r}")

        tracer = Tracer()
        started = time.monotonic()
        pending = state.pending
        state.pending = None
        state.status = RunStatus.RUNNING

        await self.chain.on_run_start(state)
        try:
            await self._apply_decision(state, tracer, pending, decision)
            deferred = state.scratch.pop("deferred_calls", [])
            if deferred:
                calls = [ToolCall.model_validate(c) for c in deferred]
                await self._run_tool_calls(calls, state, tracer)
        except _Pause as pause:
            result = await self._pause(state, tracer, pause)
        else:
            await self.checkpoint.put(state)
            result = await self._loop(state, tracer, started)
        await self.chain.on_run_end(state, result)
        return result

    # -- sync facade (generated on top; never a second engine) --------------

    def run_sync(self, input: str, *, session_id: str | None = None) -> Result:
        return anyio.run(functools.partial(self.run, input, session_id=session_id))

    def resume_sync(self, token: str, decision: Any = "approve") -> Result:
        return anyio.run(functools.partial(self.resume, token, decision))

    # -- internals ----------------------------------------------------------

    async def _start(self, input: str, session_id: str | None) -> State:
        state: State | None = None
        if session_id is not None:
            state = await self.checkpoint.get(session_id)
        if state is None:
            state = State(session_id=session_id or _new_session_id())
            if self.system:
                state.add_message(Message.system(self.system))
        state.add_message(Message.user(input))
        state.status = RunStatus.RUNNING
        await self.checkpoint.put(state)
        return state

    async def _loop(
        self,
        state: State,
        tracer: Tracer,
        started: float,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Result:
        while True:
            if should_cancel is not None and should_cancel():
                # Cooperative cancel: the current step has finished and state is
                # checkpointed, so the run is resumable from here.
                tracer.emit(
                    EventType.GUARD_TRIP, step=state.step, reason=StopReason.CANCELLED.value
                )
                state.status = RunStatus.DONE
                await self.checkpoint.put(state)
                return self._result(
                    state, tracer, StopReason.CANCELLED, answer=self._last_text(state)
                )

            trip = self.guards.check(state, time.monotonic() - started)
            if trip is not None:
                tracer.emit(EventType.GUARD_TRIP, step=state.step, reason=trip.value)
                state.status = RunStatus.DONE
                await self.checkpoint.put(state)
                return self._result(state, tracer, trip, answer=self._last_text(state))

            state.step += 1
            tracer.emit(EventType.STEP_START, step=state.step)

            ctx = StepContext(state, state.messages, list(self.tools.values()), self.provider)
            try:
                await self.chain.before_model(ctx)

                # A middleware (e.g. Cache) may preset ctx.response to serve a
                # hit; only call the provider when nothing did.
                if ctx.response is None:
                    schemas = [t.schema for t in ctx.tools]
                    tracer.emit(EventType.MODEL_CALL, step=state.step, messages=len(ctx.messages))
                    response = await self._complete(ctx, schemas, state, tracer, started)
                    if isinstance(response, Result):  # error path bubbled a Result
                        return response
                    ctx.response = response
                else:
                    tracer.emit(EventType.MODEL_CALL, step=state.step, cached=True)

                # after_model runs *before* usage is banked so a cost-tracking
                # middleware can rewrite response.usage and have it count.
                await self.chain.after_model(ctx)
                response = ctx.response
                state.add_usage(response.usage)

                msg = response.message
                state.add_message(msg)
                tracer.emit(
                    EventType.MODEL_RESPONSE,
                    step=state.step,
                    tool_calls=[c.name for c in msg.tool_calls],
                    cost_usd=state.usage.cost_usd,
                    tokens=state.usage.total_tokens,
                )

                if not msg.tool_calls and not ctx.force_continue:
                    state.status = RunStatus.DONE
                    tracer.emit(EventType.FINAL, step=state.step)
                    await self.checkpoint.put(state)
                    return self._result(state, tracer, StopReason.FINAL, answer=msg.content)

                if msg.tool_calls:
                    await self._run_tool_calls(msg.tool_calls, state, tracer)
            except _Pause as pause:
                return await self._pause(state, tracer, pause)
            except StopRun as stop:
                return await self._stop_run(state, tracer, stop)

            await self.checkpoint.put(state)

    async def _complete(
        self,
        ctx: StepContext,
        schemas: list[dict[str, Any]],
        state: State,
        tracer: Tracer,
        started: float,
    ) -> Any:
        """Call the provider, dispatching ``on_error`` actions (retry/fallback).

        The retry loop is itself bounded: the wall-clock guard is re-checked
        before every attempt and a hard attempt cap prevents a misbehaving
        ``on_error`` middleware from looping forever inside a single step.
        """
        while True:
            if (
                self.guards.timeout_s is not None
                and (time.monotonic() - started) >= self.guards.timeout_s
            ):
                tracer.emit(EventType.GUARD_TRIP, step=state.step, reason=StopReason.TIMEOUT.value)
                state.status = RunStatus.DONE
                await self.checkpoint.put(state)
                return self._result(
                    state, tracer, StopReason.TIMEOUT, answer=self._last_text(state)
                )
            if ctx.attempt >= _MAX_PROVIDER_ATTEMPTS:
                state.status = RunStatus.ERROR
                await self.checkpoint.put(state)
                return self._result(
                    state,
                    tracer,
                    StopReason.ERROR,
                    error=f"provider retry cap ({_MAX_PROVIDER_ATTEMPTS}) exceeded",
                )

            provider = ctx.provider or self.provider
            try:
                return await provider.complete(ctx.messages, schemas)
            except Exception as err:  # noqa: BLE001 - delegated to middleware policy
                action = await self.chain.on_error(ctx, err)
                tracer.emit(EventType.ERROR, step=state.step, error=str(err), action=action.value)
                if action in (ErrorAction.RETRY, ErrorAction.FALLBACK):
                    ctx.attempt += 1
                    continue
                state.status = RunStatus.ERROR
                await self.checkpoint.put(state)
                return self._result(state, tracer, StopReason.ERROR, error=str(err))

    async def _run_tool_calls(self, calls: list[ToolCall], state: State, tracer: Tracer) -> None:
        # Parallel fan-out is only safe when no call in the batch needs approval
        # (HITL pauses are inherently sequential). Manual Interrupt inside a
        # parallel tool is downgraded to an error result.
        approvals = any((self.tools.get(c.name) and self.tools[c.name].approve) for c in calls)
        if self.parallel_tools and len(calls) > 1 and not approvals:
            messages: list[Message | None] = [None] * len(calls)

            async def worker(index: int, call: ToolCall) -> None:
                messages[index] = await self._resolve_tool_call(
                    call, state, tracer, allow_pause=False
                )

            async with anyio.create_task_group() as tg:
                for index, call in enumerate(calls):
                    tg.start_soon(worker, index, call)
            for message in messages:
                if message is not None:
                    state.add_message(message)
            return

        for index, call in enumerate(calls):
            try:
                message = await self._resolve_tool_call(call, state, tracer, allow_pause=True)
            except _Pause as pause:
                pause.remaining = calls[index + 1 :]
                raise
            state.add_message(message)

    async def _resolve_tool_call(
        self, call: ToolCall, state: State, tracer: Tracer, *, allow_pause: bool
    ) -> Message:
        """Run one tool call and return its result message (does not append)."""
        tool = self.tools.get(call.name)
        tctx = ToolContext(state, tool, call)
        await self.chain.before_tool(tctx)

        if tool is None:
            tracer.emit(
                EventType.TOOL_RESULT, step=state.step, tool=call.name, error="unknown_tool"
            )
            return Message.tool(f"Error: unknown tool '{call.name}'", call.id, call.name)

        if tool.approve and allow_pause:
            payload = {"tool": call.name, "arguments": tctx.args}
            raise _Pause(call, "approve", payload, [])

        if tctx.skip:  # idempotency / replay preset the result
            content = _stringify(tctx.result)
            tracer.emit(EventType.TOOL_RESULT, step=state.step, tool=call.name, result=content)
            return Message.tool(content, call.id, call.name)

        tracer.emit(EventType.TOOL_CALL, step=state.step, tool=call.name, arguments=tctx.args)
        try:
            if tctx.timeout_s is not None:
                with anyio.fail_after(tctx.timeout_s):
                    tctx.result = await tool.call(tctx.args)
            else:
                tctx.result = await tool.call(tctx.args)
        except Interrupt as intr:
            if allow_pause:
                raise _Pause(call, "manual", intr.payload, []) from None
            tctx.result = (
                f"Error: tool '{call.name}' requested human input (not allowed in parallel)"
            )
        except Exception as err:  # noqa: BLE001 - surfaced to the model, not fatal
            tctx.error = err
            tctx.result = f"Error executing tool '{call.name}': {err}"

        await self.chain.after_tool(tctx)
        content = _stringify(tctx.result)
        tracer.emit(EventType.TOOL_RESULT, step=state.step, tool=call.name, result=content)
        return Message.tool(content, call.id, call.name)

    async def _apply_decision(
        self, state: State, tracer: Tracer, pending: PendingApproval, decision: Any
    ) -> None:
        call = pending.call
        if pending.mode == "approve":
            tool = self.tools.get(call.name)
            if _is_approved(decision):
                tctx = ToolContext(state, tool, call)
                await self.chain.before_tool(tctx)
                if tool is None:
                    content = f"Error: unknown tool '{call.name}'"
                else:
                    try:
                        tctx.result = await tool.call(tctx.args)
                    except Interrupt as intr:
                        raise _Pause(call, "manual", intr.payload, []) from None
                    except Exception as err:  # noqa: BLE001
                        tctx.result = f"Error executing tool '{call.name}': {err}"
                    await self.chain.after_tool(tctx)
                    content = _stringify(tctx.result)
                tracer.emit(EventType.TOOL_RESULT, step=state.step, tool=call.name, result=content)
            else:
                content = f"Tool '{call.name}' was rejected by human: {decision!r}"
                tracer.emit(EventType.TOOL_RESULT, step=state.step, tool=call.name, rejected=True)
        else:  # manual interrupt: the decision *is* the tool result
            content = _stringify(decision)
        state.add_message(Message.tool(content, call.id, call.name))

    async def _stop_run(self, state: State, tracer: Tracer, stop: StopRun) -> Result:
        """Convert a middleware ``StopRun`` into a structured Result."""
        is_error = stop.reason is StopReason.ERROR
        tracer.emit(EventType.GUARD_TRIP, step=state.step, reason=stop.reason.value)
        state.status = RunStatus.ERROR if is_error else RunStatus.DONE
        await self.checkpoint.put(state)
        return self._result(
            state,
            tracer,
            stop.reason,
            answer=None if is_error else (stop.message or None),
            error=stop.message if is_error else None,
        )

    async def _pause(self, state: State, tracer: Tracer, pause: _Pause) -> Result:
        state.pending = PendingApproval(call=pause.call, mode=pause.mode, payload=pause.payload)
        if pause.remaining:
            state.scratch["deferred_calls"] = [c.model_dump() for c in pause.remaining]
        state.status = RunStatus.INTERRUPTED
        await self.checkpoint.put(state)
        tracer.emit(EventType.INTERRUPT, step=state.step, mode=pause.mode, payload=pause.payload)
        # The session id *is* the resume token: it points at the durable
        # checkpoint, so the pause survives a process restart.
        return self._result(
            state,
            tracer,
            StopReason.INTERRUPT,
            resume_token=state.session_id,
            interrupt=pause.payload,
        )

    def _result(
        self,
        state: State,
        tracer: Tracer,
        reason: StopReason,
        *,
        answer: str | None = None,
        error: str | None = None,
        resume_token: str | None = None,
        interrupt: Any = None,
    ) -> Result:
        result = Result(
            answer=answer,
            stopped_reason=reason,
            state=state,
            trace=tracer.events,
            usage=state.usage,
            error=error,
            resume_token=resume_token,
            interrupt=interrupt,
        )
        self.last_result = result
        return result

    @staticmethod
    def _last_text(state: State) -> str | None:
        for message in reversed(state.messages):
            if message.role.value == "assistant" and message.content:
                return message.content
        return None
