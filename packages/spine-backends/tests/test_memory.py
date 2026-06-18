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
