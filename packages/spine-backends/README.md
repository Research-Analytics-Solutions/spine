# spine-backends

Durable storage backends for Spine.

## SQLite checkpoint

A `CheckpointStore` that survives process restarts — the durable backing for
crash recovery and long-lived human-in-the-loop pauses.

```python
from spine_core import Agent
from spine_backends import SQLiteCheckpoint

agent = Agent("anthropic:claude-sonnet-4-6", checkpoint=SQLiteCheckpoint("runs.db"))
```

Or by config: `spine.toml` `checkpoint = "sqlite"`.

- stdlib `sqlite3` offloaded to a worker thread (async-safe), WAL mode
- monotonic `revision` column for optimistic-locking checks
- `migrate()` upgrades old checkpoints to the current `STATE_VERSION` on read;
  register upgrades with `register_migration(from_version, fn)`
