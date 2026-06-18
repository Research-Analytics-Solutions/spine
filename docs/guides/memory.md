# Memory

Memory is long-term, semantic recall across sessions — distinct from a
[checkpoint store](../concepts/state.md) (durable serialization of one run). It's a
3-method protocol: `save` / `search` / `load`.

## Pick a memory type

| Type | Recall | Install |
|---|---|---|
| `InMemoryVectorMemory` | embedding cosine similarity | `spine-backends` |
| `BufferMemory` | recency (last-N), non-semantic | `spine-backends` |
| `PgVectorMemory` | Postgres + pgvector, at scale | `spine-backends[postgres]` |

```python
from spine_backends import InMemoryVectorMemory, BufferMemory

mem = InMemoryVectorMemory()        # semantic
mem = BufferMemory()                # simple recency
```

## Choose how text is embedded

Memory takes any **`Embedder`** — `async def embed(text) -> list[float]`. Swap the
default offline embedder for a real model, or bring your own:

```python
from spine_backends import InMemoryVectorMemory, HashEmbedder, OpenAIEmbedder

# offline default — deterministic, no API
mem = InMemoryVectorMemory(embedder=HashEmbedder())

# real OpenAI embeddings
mem = InMemoryVectorMemory(embedder=OpenAIEmbedder("text-embedding-3-small"), dim=1536)

# your own (sentence-transformers, Cohere, local …)
class MyEmbedder:
    async def embed(self, text: str) -> list[float]:
        return my_model.encode(text).tolist()

mem = InMemoryVectorMemory(embedder=MyEmbedder())
```

## Use it directly

```python
await mem.save("The launch code is alpha-seven.", session_id="s1")
hits = await mem.search("what is the launch code?", k=3)
print(hits[0].record.content, hits[0].score)
```

## Wire it into an agent

`MemoryRecall` searches memory by the user's question, injects matches as an
ephemeral system message (non-destructive), and saves the exchange afterward:

```python
from spine_core import Agent
from spine_middleware import MemoryRecall

agent = Agent("openai:gpt-4o-mini", middleware=[MemoryRecall(mem, k=3)])
```

Scope recall to the current session with `MemoryRecall(mem, scope_session=True)`.

## pgvector at scale

```python
from spine_backends import PgVectorMemory, OpenAIEmbedder

mem = PgVectorMemory(
    "postgresql://localhost/app",
    embedder=OpenAIEmbedder(),
    dim=1536,
)
```

Requires the `pgvector` extension in the database; the table is created on first
use.
