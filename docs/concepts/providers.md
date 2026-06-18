# Providers & models

A provider is a one-method object: `complete(messages, tools) -> ModelResponse`.
That's the entire contract the kernel depends on. An optional `stream(...)` adds
token streaming.

```python
from spine_core import Provider, Message, ModelResponse

class MyProvider:
    async def complete(self, messages, tools=None, **kw) -> ModelResponse:
        ...
```

Because the contract is this small, **nothing in the kernel knows about any
specific vendor** — you can target any model.

## The registry

Providers register under a scheme so a string resolves to one:

```python
from spine_core import register_provider

register_provider("myllm", lambda model: MyProvider(model))
agent = Agent("myllm:some-model")
```

Installed adapters self-register on import. `spine-providers` registers
`openai:` and `anthropic:`.

## Streaming

If a provider implements `stream`, `agent.stream()` emits a `token` trace event per
delta and assembles the final response:

```python
async for event in agent.stream("write a haiku"):
    if event.type == "token":
        print(event.data["delta"], end="")
```

`run()` stays non-streaming. See [Tracing, streaming & replay](observability.md).

## The router

A router is itself a provider that wraps an ordered list and applies fallback
policies — so the kernel is oblivious to whether it's talking to one model or
many. Use [`ModelFallback`](../reference/middleware.md) middleware for
error-driven failover.

For the full list of supported and reachable models, see
[Models & any provider](../guides/models.md).
