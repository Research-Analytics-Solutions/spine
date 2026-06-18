# Models & any provider

Spine is **provider-agnostic**. It ships two native adapters and reaches a dozen
more with no new code.

## Native adapters

```python
agent = Agent("openai:gpt-4o-mini")
agent = Agent("anthropic:claude-sonnet-4-6")  # needs spine-providers + ANTHROPIC_API_KEY
```

Both read their key from the environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

## Any OpenAI-compatible endpoint

A huge part of the ecosystem speaks the OpenAI API. Point `OpenAIProvider` at a
different `base_url` by injecting a client — **no new adapter needed**:

```python
import openai
from spine_core import Agent
from spine_providers import OpenAIProvider

# Ollama (local)
agent = Agent(provider=OpenAIProvider(
    "llama3.1",
    client=openai.AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
))

# Groq / Together / Fireworks / OpenRouter / DeepSeek / Azure / vLLM / LM Studio …
agent = Agent(provider=OpenAIProvider(
    "llama-3.1-70b",
    client=openai.AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=KEY),
))
```

This covers **Ollama, vLLM, LM Studio, Groq, Together, Fireworks, OpenRouter,
DeepSeek, Mistral, Azure OpenAI**, and **Gemini's OpenAI-compatible endpoint**.

## Bring your own model

Anything with an async call can be a provider. Implement one method:

```python
from spine_core import Message, ModelResponse, Usage, register_provider

class EchoProvider:
    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(self, messages, tools=None, **kw) -> ModelResponse:
        last = next(m for m in reversed(messages) if m.role.value == "user")
        return ModelResponse(
            message=Message.assistant(f"echo: {last.content}"),
            usage=Usage(input_tokens=1, output_tokens=1),
        )

register_provider("echo", lambda model: EchoProvider(model))
agent = Agent("echo:v1")
```

Add `async def stream(...)` (yielding `StreamChunk`) for token streaming. Package
it as `spine-provider-<name>` with an entry point and it becomes installable.

## Failover across providers

```python
from spine_middleware import ModelFallback

agent = Agent(
    "openai:gpt-4o-mini",
    middleware=[ModelFallback("anthropic:claude-sonnet-4-6", "openai:gpt-4o")],
)
```

On a provider error the kernel switches to the next provider for that step.

## Cost tracking for non-native models

Native adapters price their own usage. For others, add `CostTracking` so cost
guards and reports work:

```python
from spine_middleware import CostTracking

agent = Agent(provider=my_provider, middleware=[CostTracking(input_per_mtok=0.20, output_per_mtok=0.80)])
```
