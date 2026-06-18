"""Name registries for middleware and checkpoint backends.

Mirrors the provider registry (see :mod:`spine_core.provider`): plugins register
a factory under a name, and config (``spine.toml``) or code resolves it by that
name. This is what lets a declarative ``chain = ["Retry", "Compaction"]`` become
real middleware instances without the kernel knowing any of them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from spine_core.checkpoint import CheckpointStore, InMemoryCheckpointStore
from spine_core.errors import SpineError

MiddlewareFactory = Callable[..., Any]
CheckpointFactory = Callable[..., CheckpointStore]

_MIDDLEWARE: dict[str, MiddlewareFactory] = {}
_CHECKPOINT: dict[str, CheckpointFactory] = {}


def register_middleware(name: str, factory: MiddlewareFactory) -> None:
    _MIDDLEWARE[name] = factory


def resolve_middleware(name: str, **config: Any) -> Any:
    factory = _MIDDLEWARE.get(name)
    if factory is None:
        known = ", ".join(sorted(_MIDDLEWARE)) or "<none installed>"
        raise SpineError(f"no middleware registered as '{name}'. Installed: {known}")
    return factory(**config)


def list_middleware() -> list[str]:
    return sorted(_MIDDLEWARE)


def register_checkpoint(name: str, factory: CheckpointFactory) -> None:
    _CHECKPOINT[name] = factory


def resolve_checkpoint(name: str, **config: Any) -> CheckpointStore:
    factory = _CHECKPOINT.get(name)
    if factory is None:
        known = ", ".join(sorted(_CHECKPOINT)) or "<none installed>"
        raise SpineError(f"no checkpoint backend registered as '{name}'. Installed: {known}")
    return factory(**config)


def list_checkpoints() -> list[str]:
    return sorted(_CHECKPOINT)


# Built-in: the in-memory store ships with the kernel.
register_checkpoint("memory", lambda **_: InMemoryCheckpointStore())
