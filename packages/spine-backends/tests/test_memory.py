"""Vector memory backend: similarity ranking, session scoping, load."""

from __future__ import annotations

from spine_backends import InMemoryVectorMemory


async def test_search_ranks_by_similarity() -> None:
    mem = InMemoryVectorMemory()
    await mem.save("the cat sat on the mat")
    await mem.save("python is a programming language")
    await mem.save("dogs and cats are pets")

    hits = await mem.search("tell me about cats and pets", k=2)
    assert len(hits) == 2
    # the pets/cats record should outrank the python one
    assert "pets" in hits[0].record.content or "cat" in hits[0].record.content
    assert hits[0].score >= hits[1].score
    assert all("python" not in h.record.content for h in hits[:1])


async def test_session_scoping_and_load() -> None:
    mem = InMemoryVectorMemory()
    await mem.save("alpha note", session_id="s1")
    await mem.save("beta note", session_id="s2")

    scoped = await mem.search("note", k=5, session_id="s1")
    assert [h.record.content for h in scoped] == ["alpha note"]

    loaded = await mem.load("s2")
    assert [r.content for r in loaded] == ["beta note"]


async def test_registry_resolves_vector_memory() -> None:
    import spine_backends  # noqa: F401  (registers backends)
    from spine_core import resolve_memory

    mem = resolve_memory("vector", dim=128)
    assert isinstance(mem, InMemoryVectorMemory)
    assert mem.dim == 128


async def test_custom_embedder_is_used() -> None:
    from spine_backends import InMemoryVectorMemory

    class TagEmbedder:
        """Embeds 'a'->[1,0], everything else ->[0,1]."""

        async def embed(self, text: str) -> list[float]:
            return [1.0, 0.0] if "apple" in text else [0.0, 1.0]

    mem = InMemoryVectorMemory(embedder=TagEmbedder())
    await mem.save("apple pie recipe")
    await mem.save("car engine repair")
    hits = await mem.search("fresh apple", k=1)
    assert "apple" in hits[0].record.content
    assert hits[0].score == 1.0


async def test_buffer_memory_returns_recent() -> None:
    from spine_backends import BufferMemory

    mem = BufferMemory()
    for i in range(5):
        await mem.save(f"note {i}", session_id="s")
    hits = await mem.search("anything", k=2, session_id="s")
    assert [h.record.content for h in hits] == ["note 4", "note 3"]


async def test_openai_embedder_with_fake_client() -> None:
    from types import SimpleNamespace

    from spine_backends import OpenAIEmbedder

    class FakeEmbeddings:
        async def create(self, *, model, input):  # type: ignore[no-untyped-def]
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    client = SimpleNamespace(embeddings=FakeEmbeddings())
    embedder = OpenAIEmbedder(client=client)
    assert await embedder.embed("hi") == [0.1, 0.2, 0.3]


def test_registry_resolves_buffer_and_pgvector() -> None:
    import spine_backends  # noqa: F401
    from spine_core import list_memories

    assert {"vector", "buffer", "pgvector"} <= set(list_memories())
