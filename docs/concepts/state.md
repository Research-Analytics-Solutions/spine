# State & checkpoints

## Explicit, serializable state

Everything needed to resume a run lives in one Pydantic `State` object: the
messages, step count, accumulated usage, status, tenant id, and a scratch dict.
Because it's plain Pydantic it round-trips to JSON for durable checkpointing and
horizontal scale.

```python
from spine_core import State, Message

state = State(session_id="s1")
state.add_message(Message.user("hello"))
restored = State.model_validate_json(state.model_dump_json())
assert restored == state
```

The kernel is **stateless between steps** — all the state is here, so "scale" is
"add workers."

## Checkpoint stores

A checkpoint store is durable serialization of `State` for crash recovery and
resume — distinct from [memory](../guides/memory.md) (semantic recall). The
protocol is tiny: `put` / `get` / `delete`.

| Backend | Use | Install |
|---|---|---|
| `InMemoryCheckpointStore` | default, single process | built in |
| `SQLiteCheckpoint` | embedded, durable | `spine-backends` |
| `RedisCheckpoint` | distributed workers | `spine-backends[redis]` |
| `PostgresCheckpoint` | durable + optimistic locking | `spine-backends[postgres]` |

```python
from spine_core import Agent
from spine_backends import SQLiteCheckpoint

agent = Agent("openai:gpt-4o-mini", checkpoint=SQLiteCheckpoint("runs.db"))
```

Or by config — `spine.toml`:

```toml
[spine.backends]
checkpoint = "sqlite"
```

## Schema migration

When old checkpoints (`version=1`) are resumed by new code (`version=2`), backends
call `migrate()` on the raw dict before validating. Register upgrades:

```python
from spine_backends import register_migration

register_migration(1, lambda raw: {**raw, "version": 2, "new_field": "default"})
```

Every backend passes a shared conformance suite, so they behave identically.
