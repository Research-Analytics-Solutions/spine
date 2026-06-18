# Build a provider

A provider turns messages + tool schemas into a `ModelResponse`. The contract is
one method:

```python
async def complete(
    self,
    messages: list[Message],
    tools: list[dict] | None = None,
    **kwargs,
) -> ModelResponse: ...
```

`tools` is a list of `{"name", "description", "parameters"}` (JSON schema). Map
them to your API's tool format, and map the reply back into a `ModelResponse`.

## Minimal provider

```python exec="1" source="above" result="text"
from spine_core import Agent, Message, ModelResponse, Usage, register_provider

class EchoProvider:
    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(self, messages, tools=None, **kw) -> ModelResponse:
        last = next(m for m in reversed(messages) if m.role.value == "user")
        return ModelResponse(
            message=Message.assistant(f"echo: {last.content}"),
            usage=Usage(input_tokens=5, output_tokens=2, cost_usd=0.0),
        )

register_provider("echo", lambda model: EchoProvider(model))
print(Agent("echo:v1").run_sync("hello").answer)
```

`register_provider(scheme, factory)` makes `Agent("echo:...")` resolve. The factory
receives the part after the colon.

## Returning tool calls

If your model wants to call tools, put them on the assistant message:

```python
from spine_core import Message, ModelResponse, ToolCall, Usage

return ModelResponse(
    message=Message.assistant(
        content=None,
        tool_calls=[ToolCall(id="call_0", name="add", arguments={"a": 1, "b": 2})],
    ),
    usage=Usage(input_tokens=20, output_tokens=8),
)
```

The kernel validates the args, runs the tool, appends a `tool` message, and calls
you again — you don't manage the loop.

## Cost & usage

Set `usage.cost_usd` if you can price it (so cost guards work). If you can't, leave
it `0.0` and users add the [`CostTracking`](../reference/middleware.md) middleware
with a price table.

## Add streaming (optional)

Implement `stream` returning an async iterator of `StreamChunk` — `delta` for
incremental text, the final chunk carrying the assembled `response`:

```python
from spine_core import StreamChunk, Message, ModelResponse, Usage

class EchoProvider:
    async def complete(self, messages, tools=None, **kw) -> ModelResponse:
        ...

    async def stream(self, messages, tools=None, **kw):
        text = "echo: hi"
        for word in text.split():
            yield StreamChunk(delta=word + " ")
        yield StreamChunk(response=ModelResponse(message=Message.assistant(text), usage=Usage()))
```

`agent.stream()` then emits a `token` trace event per delta. `run()` still uses
`complete`.

## Reuse OpenAI-compatibility

If your endpoint speaks the OpenAI API, you don't need a new provider at all —
point `OpenAIProvider` at its `base_url`. See [Models](../guides/models.md).

## Package it

`spine-provider-<name>` with an entry point that self-registers on import — see
[Publish a plugin](publish.md).
