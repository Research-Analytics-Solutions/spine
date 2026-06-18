# Spine

A lightweight, modular, protocol-native runtime for production AI agents.

A tiny, load-bearing kernel that everything else plugs into via **opt-in
middleware, swappable backends, and protocol adapters** — lightweight and
complete at the same time. See [`CLAUDE.md`](./CLAUDE.md) for the full
architecture & delivery plan.

## Layout (uv workspace monorepo)

```
spine/
├── packages/
│   └── spine-core/     # the kernel: loop, state, guards, tracer, protocols  ✅ V1 in progress
├── pyproject.toml      # uv workspace + dev tooling (ruff, mypy, pytest)
└── CLAUDE.md           # architecture & delivery plan
```

Planned packages (per `CLAUDE.md` §14): `spine-cli`, `spine-providers`,
`spine-mcp`, `spine-a2a`, `spine-otel`, `spine-backends`, `spine-eval`.

## Develop

```bash
uv sync               # install workspace + dev deps
uv run pytest         # tests
uv run ruff check .   # lint
uv run ruff format .  # format
uv run mypy           # strict type-check
```

## Quickstart

```python
from spine_core import Agent
from spine_core.testing import ScriptedProvider, text

agent = Agent(ScriptedProvider(text("hello from spine")))
print(agent.run_sync("hi").answer)   # -> "hello from spine"
```

Real providers register under a `scheme:model` string
(`Agent("anthropic:claude-sonnet-4-6")`) via plugin entry points; the kernel
itself ships only the protocol.
