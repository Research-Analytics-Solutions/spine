# spine-providers

Model provider adapters for Spine. Each implements the core `Provider` protocol
(`async def complete(messages, tools) -> ModelResponse`) and registers under a
`scheme:model` string.

## Anthropic

```python
import spine_providers            # registers the "anthropic:" scheme
from spine_core import Agent

agent = Agent("anthropic:claude-sonnet-4-6")   # reads ANTHROPIC_API_KEY
print((await agent.run("say hi")).answer)
```

The SDK client is created lazily, so resolving a provider never needs a key or
network. Translation between Spine messages and the Anthropic Messages API lives
in pure functions (`to_anthropic_messages`, `to_anthropic_tools`,
`from_anthropic_response`) and is unit-tested without the network.
