# Installation

Spine ships as a single package, **`spinekit`**, with a lean core and opt-in
extras. The import name stays `spine_core` (etc.).

```bash
# the kernel — only Pydantic + anyio
pip install spinekit            # or: uv add spinekit
```

The full Spine code is installed (it's small); the **heavy dependencies** are
extras, so your project pulls only what it uses.

## Extras

```bash
pip install "spinekit[openai]"            # OpenAI provider
pip install "spinekit[anthropic]"         # Anthropic provider
pip install "spinekit[providers]"         # both
pip install "spinekit[cli]"               # the spine CLI (Typer + Rich)
pip install "spinekit[redis]"             # Redis checkpoint
pip install "spinekit[postgres]"          # Postgres / pgvector
pip install "spinekit[mcp]"               # MCP tools
pip install "spinekit[a2a]"               # remote agents (A2A)
pip install "spinekit[otel]"              # OpenTelemetry  (+[otlp] for the exporter)
pip install "spinekit[eval]"              # the eval harness (YAML datasets)
pip install "spinekit[all]"               # everything
```

Combine them: `pip install "spinekit[openai,redis,cli]"`.

| Extra | Pulls | For |
|---|---|---|
| `openai` / `anthropic` / `providers` | the provider SDK(s) | native models |
| `cli` | typer, rich | the `spine` command |
| `redis` / `postgres` | redis / asyncpg | distributed checkpoints, pgvector |
| `mcp` / `a2a` | mcp / httpx | MCP tools, remote agents |
| `otel` / `otlp` | opentelemetry | observability |
| `eval` | pyyaml | YAML eval datasets |
| `all` | all of the above | kitchen sink |

!!! note "What's always there"
    `spine_core`, `spine_middleware`, `spine_backends` (SQLite + in-memory),
    `spine_orchestration` need no extra — their code ships with the base install
    and depends only on the standard library + Pydantic + anyio.

## Requirements

- Python **3.12+**
- Base install pulls only **Pydantic v2** and **anyio**.

## Any OpenAI-compatible endpoint

No extra beyond `[openai]` — point the client at a `base_url` (Ollama, vLLM,
Groq, …). See [Models & any provider](guides/models.md).

## Scaffold a project

```bash
pip install "spinekit[cli]"
spine init my-agent
cd my-agent && spine doctor
```

See the [CLI reference](reference/cli.md) for the generated layout.
