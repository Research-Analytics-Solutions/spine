# Publish a plugin

A Spine plugin is an **ordinary Python package** that registers itself via an
entry point. No special framework, no custom loader — the same mechanism pytest
and Flask use.

## 1. Name it by convention

| Kind | Package name |
|---|---|
| provider | `spine-provider-<name>` |
| middleware | `spine-mw-<name>` |
| backend | `spine-backend-<name>` |
| adapter | `spine-<name>` |

## 2. Lay it out

```
spine-mw-profanity/
├── pyproject.toml
└── src/
    └── spine_mw_profanity/
        └── __init__.py
```

```python
# src/spine_mw_profanity/__init__.py
from spine_core import StepContext, StopRun, StopReason, register_middleware

class ProfanityFilter:
    def __init__(self, words: list[str] | None = None) -> None:
        self.words = set(words or ["badword"])

    async def after_model(self, ctx: StepContext) -> None:
        msg = ctx.response.message
        if msg.content and any(w in msg.content.lower() for w in self.words):
            raise StopRun(StopReason.GUARDRAIL, "profanity blocked")

def register() -> None:
    register_middleware("ProfanityFilter", ProfanityFilter)

register()   # self-register on import
```

## 3. Declare the entry point

```toml
# pyproject.toml
[project]
name = "spine-mw-profanity"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["spine-core>=0.1,<1.0"]

[project.entry-points."spine.plugins"]
mw_profanity = "spine_mw_profanity:ProfanityFilter"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The entry point target should point at something whose **import triggers
`register()`** — pointing at the package (`spine_mw_profanity:ProfanityFilter`)
means loading it imports `__init__`, which self-registers. `spine plugin list` and
`spine doctor` discover it; `spine.toml` can then name `ProfanityFilter`.

## 4. Use it — three ways

=== "From PyPI"

    ```bash
    uv add spine-mw-profanity
    ```

=== "From a GitHub link"

    No PyPI needed — install straight from a repo:

    ```bash
    uv add "spine-mw-profanity @ git+https://github.com/you/spine-mw-profanity"
    # a branch / tag / commit:
    uv add "spine-mw-profanity @ git+https://github.com/you/spine-mw-profanity@v0.1.0"
    ```

=== "Local path (developing)"

    ```bash
    uv add --editable ../spine-mw-profanity
    ```

Once installed, it works from code and from `spine.toml` with no extra wiring:

```python
import spine_mw_profanity   # registers on import
agent = Agent("openai:gpt-4o-mini", middleware=[spine_mw_profanity.ProfanityFilter()])
```

## 5. Publish to PyPI

```bash
uv build                       # builds wheel + sdist into dist/
uv publish                     # uploads (uses your PyPI token)
```

## Compatibility & trust

- **Pin a core range:** `dependencies = ["spine-core>=0.1,<1.0"]`. The kernel's
  hook points and protocols are the stable plugin ABI, versioned with SemVer; a
  breaking change requires a major bump.
- **Heavy deps go in extras** so a base install stays light (see
  [Build a backend](backend.md#keep-heavy-drivers-optional)).
- `spine plugin list` flags third-party plugins; enterprises can gate them with an
  allowlist.

That's it — a plugin is just a package with an entry point. Share a GitHub link and
anyone can `uv add` it.
