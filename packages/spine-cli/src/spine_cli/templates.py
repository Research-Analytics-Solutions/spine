"""Project scaffolding rendered by ``spine init``.

Each template is a thin, runnable starting point. ``minimal`` is the only one
wired up for V1; richer templates (chatbot, rag, multi-agent, …) follow.
"""

from __future__ import annotations

TEMPLATES = ("minimal",)

_PYPROJECT = """\
[project]
name = "{name}"
version = "0.1.0"
description = "A Spine agent."
requires-python = ">=3.12"
dependencies = [
    "spinekit[anthropic,cli,eval]",
]
"""

_SPINE_TOML = """\
[spine]
default_model = "anthropic:claude-sonnet-4-6"

[spine.guards]
max_steps = 8
max_cost_usd = 0.50
timeout_s = 30

[spine.middleware]
chain = []

[spine.backends]
checkpoint = "memory"
"""

_ENV_EXAMPLE = """\
# Copy to .env and fill in. Never commit real secrets.
ANTHROPIC_API_KEY=
"""

_ASSISTANT = '''\
"""The project's agent. ``spine run assistant "hello"`` executes it."""

from __future__ import annotations

import spine_providers  # noqa: F401 — registers the "anthropic:" provider scheme

from spine_core import Agent

from tools import echo

agent = Agent(
    "anthropic:claude-sonnet-4-6",
    tools=[echo],
    system="You are a helpful assistant. Be concise.",
)
'''

_TOOLS = '''\
"""@tool functions, auto-discovered. Add your own here."""

from __future__ import annotations

from spine_core import tool


@tool
async def echo(text: str) -> str:
    """Echo the text straight back."""
    return text


__all__ = ["echo"]
'''

_README = """\
# {name}

A Spine agent. Scaffolded with `spine init`.

```bash
uv sync
export ANTHROPIC_API_KEY=sk-...
uv run spine run assistant "say hello"   # the agent defined in agents/
uv run spine chat "say hello"            # the agent built from spine.toml
uv run spine trace                        # inspect recorded run traces
uv run spine doctor
```
"""

_GITIGNORE = """\
__pycache__/
*.py[oc]
.venv
.env
.spine/
"""

_SMOKE_EVAL = """\
cases:
  - id: greeting
    input: "say hello"
    expected: "hello"
"""


def render(name: str, template: str = "minimal") -> dict[str, str]:
    """Return a mapping of relative path -> file content for a new project."""
    if template not in TEMPLATES:
        raise ValueError(f"unknown template '{template}'. Available: {', '.join(TEMPLATES)}")
    return {
        "pyproject.toml": _PYPROJECT.format(name=name),
        "spine.toml": _SPINE_TOML,
        ".env.example": _ENV_EXAMPLE,
        ".gitignore": _GITIGNORE,
        "agents/assistant.py": _ASSISTANT,
        "tools/__init__.py": _TOOLS,
        "evals/smoke.yaml": _SMOKE_EVAL,
        "README.md": _README.format(name=name),
    }
