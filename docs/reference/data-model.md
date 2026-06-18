# Data model & wire shapes

Every boundary in Spine is a typed Pydantic model. This page shows the exact
structure of each, and what a request to a provider and a response look like.

## Message

A single conversational turn. The kernel and every provider speak in these.

| Field | Type | Notes |
|---|---|---|
| `role` | `"system" \| "user" \| "assistant" \| "tool"` | who authored it |
| `content` | `str \| None` | text; `None` on an assistant turn that only calls tools |
| `parts` | `list[dict] \| None` | multimodal blocks; when set, providers send these instead of `content` |
| `tool_calls` | `list[ToolCall]` | present on an assistant turn that calls tools |
| `tool_call_id` | `str \| None` | on a `tool` result, links back to the request |
| `name` | `str \| None` | optional tool name on a `tool` result |

Constructors: `Message.system(text)`, `Message.user(text)`,
`Message.user_parts(parts)`, `Message.assistant(content, tool_calls)`,
`Message.tool(content, tool_call_id, name)`.

### What the messages look like

A full tool round-trip, as JSON:

```json
[
  {"role": "system", "content": "You are concise."},
  {"role": "user", "content": "add 17 and 25"},
  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_0", "name": "add", "arguments": {"a": 17, "b": 25}}
  ]},
  {"role": "tool", "tool_call_id": "call_0", "name": "add", "content": "42"},
  {"role": "assistant", "content": "42"}
]
```

### Multimodal

```python
from spine_core import Message, text_part, image_part

msg = Message.user_parts([
    text_part("What is in this image?"),
    image_part(url="https://example.com/cat.png"),
    image_part(data="<base64>", media_type="image/jpeg"),
])
```

Each part is `{"type": "text", "text": ...}` or
`{"type": "image", "url": ...}` / `{"type": "image", "data": ..., "media_type": ...}`.
Providers translate to their native block shape.

## ToolCall

```python
ToolCall(id="call_0", name="add", arguments={"a": 17, "b": 25})
```

`arguments` are the model's **raw** (unvalidated) args; the kernel validates them
against the tool's schema before executing.

## ModelResponse

What a provider returns from `complete`:

| Field | Type |
|---|---|
| `message` | `Message` (the assistant turn) |
| `usage` | `Usage` |
| `finish_reason` | `str \| None` |
| `raw` | provider-native payload (excluded from serialization) |

## Usage

```python
Usage(input_tokens=10, output_tokens=5, cost_usd=0.000105)
```

`.total_tokens` is a property; `usage_a + usage_b` combines them. `cost_usd` is set
by native providers or the `CostTracking` middleware.

## Result

The outcome of `run()` / `resume()`:

| Field | Type | When |
|---|---|---|
| `answer` | `str \| None` | the final text |
| `stopped_reason` | `StopReason` | always |
| `state` | `State` | the full final state |
| `trace` | `list[TraceEvent]` | every step |
| `usage` | `Usage` | totals |
| `resume_token` | `str \| None` | only on `interrupt` |
| `interrupt` | `Any` | only on `interrupt` (the payload) |
| `error` | `str \| None` | only on `error` |

Helpers: `result.ok` (stopped final), `result.interrupted`.

```python
result = await agent.run("…")
result.answer            # "42"
result.stopped_reason    # StopReason.FINAL
result.usage.cost_usd    # 0.000105
result.state.step        # 2
```

### StopReason

`final` · `max_steps` · `max_cost` · `max_tokens` · `timeout` · `max_depth` ·
`loop` · `guardrail` · `interrupt` · `error` · `cancelled`

## State

The complete, resumable state of one run — serializes to JSON.

| Field | Type | Notes |
|---|---|---|
| `version` | `int` | schema version (migrated on resume) |
| `session_id` | `str` | the run id; also the resume token |
| `tenant_id` | `str \| None` | for per-tenant budgets/isolation |
| `messages` | `list[Message]` | full history |
| `step` | `int` | model turns taken |
| `usage` | `Usage` | cumulative |
| `status` | `running \| done \| interrupted \| error` | |
| `depth` | `int` | sub-agent delegation depth |
| `pending` | `PendingApproval \| None` | set when paused for HITL |
| `scratch` | `dict` | middleware working storage (loop history, structured output, …) |

```python
restored = State.model_validate_json(state.model_dump_json())  # round-trips
```

## TraceEvent

One per kernel transition; retained in `Result.trace`.

| Field | Type |
|---|---|
| `seq` | `int` (monotonic) |
| `type` | event type (below) |
| `step` | `int` |
| `ts` | `float` (epoch) |
| `data` | `dict` (event-specific) |

Types: `step_start`, `model_call`, `token`, `model_response`, `tool_call`,
`tool_result`, `guard_trip`, `interrupt`, `error`, `final`.

## What middleware sees

### StepContext (model hooks)

| Attribute | Use |
|---|---|
| `state` | the live `State` |
| `messages` | messages for this call — reassign to rewrite (e.g. compaction) |
| `tools` | tools available this step |
| `response` | the `ModelResponse` (after the call); preset it to short-circuit |
| `provider` | swap for fallback |
| `attempt` | retry counter |
| `force_continue` | set `True` to loop again without a tool call |
| `extra` | scratch dict for your middleware |

### ToolContext (tool hooks)

| Attribute | Use |
|---|---|
| `state`, `tool`, `call` | the run, the `Tool`, the `ToolCall` |
| `args` | validated arguments |
| `result` | the tool result (set it + `skip` to preset) |
| `error` | the exception, if the tool raised |
| `timeout_s` | set a per-call timeout |
| `skip` | set `True` to skip execution and use `result` |
