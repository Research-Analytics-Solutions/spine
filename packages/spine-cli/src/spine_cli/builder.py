"""Build a live :class:`Agent` from declarative ``spine.toml`` config.

This closes the gap between the declared config (model, guards, middleware chain,
checkpoint backend) and a running agent: names in the chain are resolved through
the core registries, which installed plugins populate.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from spine_cli.config import SpineConfig
from spine_cli.plugins import load_all
from spine_core import (
    Agent,
    Provider,
    Result,
    Tool,
    resolve_checkpoint,
    resolve_middleware,
)

TRACES_DIR = ".spine/traces"


def _ensure_on_path(project_root: Path) -> None:
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)


def discover_tools(project_root: Path) -> list[Tool]:
    """Collect ``@tool`` instances exposed by the project's ``tools`` package."""
    _ensure_on_path(project_root)
    # Drop any cached "tools" so discovery always reads the current project's.
    sys.modules.pop("tools", None)
    try:
        module = importlib.import_module("tools")
    except ImportError:
        return []
    return [value for value in vars(module).values() if isinstance(value, Tool)]


def build_agent(
    config: SpineConfig,
    project_root: Path,
    *,
    provider: Provider | str | None = None,
) -> Agent:
    """Construct an Agent from config: model, guards, middleware, backend, tools."""
    load_all()  # import installed plugins so registry names resolve

    middleware = [
        resolve_middleware(name, **config.plugins.get(name, {})) for name in config.middleware.chain
    ]
    checkpoint = None
    if config.backends.checkpoint:
        backend = config.backends.checkpoint
        checkpoint = resolve_checkpoint(backend, **config.plugins.get(backend, {}))

    return Agent(
        provider or config.default_model,
        tools=discover_tools(project_root),
        guards=config.guards,
        middleware=middleware,
        checkpoint=checkpoint,
        system=config.system,
    )


def save_trace(project_root: Path, result: Result) -> Path:
    """Persist a run's trace under ``.spine/traces/<session>.json`` for `spine trace`."""
    directory = project_root / TRACES_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.state.session_id}.json"
    payload: dict[str, Any] = {
        "session_id": result.state.session_id,
        "stopped_reason": result.stopped_reason.value,
        "events": [event.model_dump() for event in result.trace],
    }
    path.write_text(json.dumps(payload, default=str, indent=2))
    return path
