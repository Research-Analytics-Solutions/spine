# Installation

Spine is a set of small packages. Install only what you use.

```bash
# the kernel — zero heavy deps (Pydantic + anyio)
uv add spine-core

# a provider adapter (OpenAI + Anthropic + any OpenAI-compatible endpoint)
uv add spine-providers

# the middleware suite (retry, guardrails, cache, memory recall, …)
uv add spine-middleware

# durable backends (SQLite/Redis/Postgres checkpoints, vector memory)
uv add spine-backends

# the CLI
uv add spine-cli
```

Other packages: `spine-mcp`, `spine-a2a`, `spine-otel`, `spine-eval`,
`spine-orchestration`.

!!! note "Optional extras"
    Some backends pull heavy drivers only when you ask:

    ```bash
    uv add 'spine-backends[redis]'      # redis.asyncio
    uv add 'spine-backends[postgres]'   # asyncpg
    uv add 'spine-otel[otlp]'           # OTLP exporter
    ```

## Requirements

- Python **3.12+**
- The kernel's only runtime dependencies are **Pydantic v2** and **anyio**.

## Scaffold a project

```bash
uv run spine init my-agent
cd my-agent && uv sync
uv run spine doctor
```

See the [CLI reference](reference/cli.md) for the generated layout.
