<p align="center">
  <img src="docs/assets/logo-hero.svg" alt="Spine" width="110" />
</p>

<h1 align="center">Spine</h1>

<p align="center">
  <strong>A lightweight, modular, protocol-native runtime for production AI agents.</strong>
</p>

<p align="center">
  <a href="https://github.com/rahulgurujala/spine/actions/workflows/ci.yml"><img src="https://github.com/rahulgurujala/spine/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+">
  <a href="https://rahulgurujala.github.io/spine/"><img src="https://img.shields.io/badge/docs-mkdocs--material-526CFE.svg" alt="Docs"></a>
</p>

<p align="center">
  <a href="https://rahulgurujala.github.io/spine/">Documentation</a> ·
  <a href="https://rahulgurujala.github.io/spine/quickstart/">Quickstart</a> ·
  <a href="https://rahulgurujala.github.io/spine/guides/examples/">Cookbook</a> ·
  <a href="https://rahulgurujala.github.io/spine/contributing/">Contributing</a>
</p>

---

Spine is the *kernel* for AI agents — a tiny, load-bearing runtime that everything
else plugs into. Where monolithic frameworks bundle heavy abstractions, Spine
ships a small core and pushes every feature into **opt-in middleware, swappable
backends, and protocol adapters**.

```python
from spine_core import Agent

agent = Agent("openai:gpt-4o-mini")
print((await agent.run("say hello")).answer)
```

## Three guarantees

- **No hidden prompts** — every model call consumes inspectable, typed `Message` objects.
- **No runaway loops** — guards are enforced inside the kernel, every iteration.
- **Deterministic replay** — any run can be recorded and replayed step-for-step.

## Install

```bash
uv add spine-core spine-providers spine-middleware
```

## What's in the box

| Package | What |
|---|---|
| `spine-core` | the kernel — loop, state, guards, tracer, protocols, HITL, streaming |
| `spine-providers` | OpenAI + Anthropic (and any OpenAI-compatible endpoint) |
| `spine-middleware` | retry, fallback, guardrails, cache, memory recall, sandbox, replay, … |
| `spine-backends` | checkpoints (SQLite/Redis/Postgres) + memory (vector/buffer/pgvector) |
| `spine-mcp` · `spine-a2a` · `spine-otel` | MCP tools · remote agents · OpenTelemetry |
| `spine-eval` | dataset + scorers + Cost/Latency/Efficacy/Reliability report |
| `spine-orchestration` | sequential / supervisor / handoff |
| `spine-cli` | `init` / `run` / `chat` / `dev` / `trace` / `eval` / `doctor` / `plugin` |

## Develop

```bash
uv sync                      # install workspace + dev deps
uv run pytest                # tests
uv run ruff check .          # lint
uv run mypy                  # strict type-check
uv run mkdocs serve          # preview docs at http://127.0.0.1:8000
```

See the [Contributing guide](https://rahulgurujala.github.io/spine/contributing/)
to build your own [middleware](https://rahulgurujala.github.io/spine/develop/middleware/),
[provider](https://rahulgurujala.github.io/spine/develop/provider/), or
[backend](https://rahulgurujala.github.io/spine/develop/publish/) and publish it
as a plugin.

## License

[MIT](LICENSE) © 2026 Rahul Gurujala
