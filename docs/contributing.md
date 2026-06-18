# Contributing

Spine is a `uv` workspace monorepo of small packages. This page gets you from
clone to a green pull request, and explains how the codebase is laid out so you
can find your way around.

## Setup

```bash
git clone https://github.com/spine/spine
cd spine
uv sync            # installs every workspace package + dev tools, editable
```

Python **3.12+** (the repo pins 3.13). The kernel's only runtime dependencies are
Pydantic v2 and anyio.

## The gates (run these before every PR)

```bash
uv run pytest              # the whole suite
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # strict type-check
```

All four must be clean. CI runs the same. A quick all-in-one:

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Repository layout

```
spine/
├── packages/
│   ├── spine-core/          # the kernel — loop, state, guards, protocols, tracer
│   ├── spine-providers/     # OpenAI, Anthropic adapters
│   ├── spine-middleware/    # the middleware suite
│   ├── spine-backends/      # checkpoints + memory backends
│   ├── spine-mcp/ spine-a2a/ spine-otel/   # protocol adapters
│   ├── spine-eval/          # eval harness
│   ├── spine-orchestration/ # multi-agent patterns
│   └── spine-cli/           # the CLI
├── docs/                    # this site (mkdocs-material)
└── pyproject.toml           # workspace + dev tooling config
```

Each package is independent: `src/<pkg>/`, `tests/`, `pyproject.toml`, `README.md`.

## Design rules (these are review gates)

1. **The kernel stays tiny.** A new feature is a **middleware**, a **backend**, or
   an **adapter** — never a kernel edit. If your feature needs to change the
   kernel, open an issue first; it usually means a missing *hook*, not a missing
   feature.
2. **Typed at every boundary.** Pydantic models, full type hints, `mypy` strict.
3. **No hidden behavior.** Everything observable via the trace.
4. **Pay for what you import.** Don't add a dependency to `spine-core`. Heavy deps
   go in the relevant package, as an optional extra where possible.

## Testing philosophy

- **No network in tests.** Drive the kernel with `ScriptedProvider`; drive provider
  adapters with an injected fake client; drive backends with a fake or a temp file.
- **Test behavior, not implementation** — assert outputs, side effects, and
  computed values (see existing tests for the style).
- New backends must pass the shared **conformance suite**
  (`packages/spine-backends/tests/test_conformance.py`).
- Live-API or DB tests are gated on env vars (`SPINE_TEST_PG_DSN`, …) and skip by
  default, so the suite is fast and offline.

## Where to add what

| You want to add… | Put it in… | Register with… |
|---|---|---|
| A model | `spine-providers` or a new `spine-provider-*` package | `register_provider` |
| A reusable middleware | `spine-middleware` or `spine-mw-*` | `register_middleware` |
| A checkpoint/memory store | `spine-backends` or `spine-backend-*` | `register_checkpoint` / `register_memory` |
| A standard adapter (MCP/A2A/…) | a new `spine-*` package | exposes tools/providers |

See [Build a middleware](develop/middleware.md), [Build a provider](develop/provider.md),
[Build a backend](develop/backend.md), and [Publish a plugin](develop/publish.md).

## Commits & PRs

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, …).
- Keep a PR focused; add tests; keep the gates green.
- Update the relevant package `README.md` and these docs if you change behavior.

## Building the docs

```bash
uv run mkdocs serve            # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict   # what CI checks — must pass clean
```

Code samples marked `python exec="1"` run at build time, so docs can't drift from
the API.
