# Build a backend

Backends sit behind tiny protocols. There are two kinds: **checkpoint stores**
(durable run state) and **memory** (semantic recall).

## A checkpoint store

Implement three async methods:

```python
from spine_core import State

class MyCheckpoint:
    async def put(self, state: State) -> None: ...
    async def get(self, session_id: str) -> State | None: ...
    async def delete(self, session_id: str) -> None: ...
```

Serialize with `state.model_dump_json()` and restore with
`State.model_validate_json(...)`. If you support [schema
migration](../concepts/state.md#schema-migration), run `migrate(json.loads(raw))`
before validating.

Register it so config can name it:

```python
from spine_core import register_checkpoint

register_checkpoint("mydb", lambda **cfg: MyCheckpoint(**cfg))
```

```toml
[spine.backends]
checkpoint = "mydb"
```

### Conformance

Every checkpoint store must behave identically. Run your store through the shared
suite — the contract is: missing → `None`, put→get round-trips, overwrite updates,
delete removes. Mirror `packages/spine-backends/tests/test_conformance.py`.

## A memory backend

Implement the `Memory` protocol — `save` / `search` / `load`:

```python
from spine_core import MemoryRecord, MemoryHit

class MyMemory:
    async def save(self, content, *, session_id=None, metadata=None) -> MemoryRecord: ...
    async def search(self, query, *, k=5, session_id=None) -> list[MemoryHit]: ...
    async def load(self, session_id, *, limit=20) -> list[MemoryRecord]: ...

from spine_core import register_memory
register_memory("mymem", lambda **cfg: MyMemory(**cfg))
```

### Pluggable embedders

Take any `Embedder` (`async def embed(text) -> list[float]`) so users choose how
text is vectorized — don't hard-code one:

```python
from spine_core import Embedder
from spine_backends import HashEmbedder

class MyMemory:
    def __init__(self, *, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or HashEmbedder()
```

## Keep heavy drivers optional

Import the driver **lazily** (inside the method that needs it) and make it an
optional extra, so importing your package never requires the dependency:

```python
def _ensure_pool(self):
    import asyncpg          # lazy
    ...
```

```toml
# your pyproject.toml
[project.optional-dependencies]
mydb = ["the-driver>=1.0"]
```

This is how `spine-backends` ships SQLite (stdlib) with Redis/Postgres as extras.

Package and publish — see [Publish a plugin](publish.md).
