"""Cache middleware: hits skip the provider, TTL expiry, zero-cost, key isolation."""

from __future__ import annotations

import anyio

from spine_core import Agent
from spine_core.messages import Message, ModelResponse, Usage
from spine_middleware import Cache


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        self.calls += 1
        return ModelResponse(
            message=Message.assistant("answer"),
            usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.01),
        )


async def test_identical_request_hits_cache_and_skips_provider() -> None:
    provider = CountingProvider()
    cache = Cache()
    agent = Agent(provider, middleware=[cache])

    first = await agent.run("hello")
    second = await agent.run("hello")

    assert first.answer == "answer"
    assert second.answer == "answer"
    assert provider.calls == 1  # second served from cache
    assert cache.hits == 1
    assert cache.misses == 1


async def test_cache_hit_is_free() -> None:
    provider = CountingProvider()
    agent = Agent(provider, middleware=[Cache()])
    first = await agent.run("price")
    second = await agent.run("price")
    assert first.usage.cost_usd == 0.01
    assert second.usage.cost_usd == 0.0  # cached response is free


async def test_distinct_inputs_miss() -> None:
    provider = CountingProvider()
    cache = Cache()
    agent = Agent(provider, middleware=[cache])
    await agent.run("a")
    await agent.run("b")
    assert provider.calls == 2
    assert cache.hits == 0


async def test_ttl_expiry_forces_refetch() -> None:
    provider = CountingProvider()
    agent = Agent(provider, middleware=[Cache(ttl_s=0.01)])
    await agent.run("hello")
    await anyio.sleep(0.02)
    await agent.run("hello")
    assert provider.calls == 2  # entry expired, provider called again


async def test_eviction_respects_max_size() -> None:
    provider = CountingProvider()
    cache = Cache(max_size=2)
    agent = Agent(provider, middleware=[cache])
    for text_in in ("a", "b", "c"):
        await agent.run(text_in)
    assert len(cache._store) == 2  # oldest evicted
