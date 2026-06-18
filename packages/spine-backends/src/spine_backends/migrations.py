"""State schema migration registry.

A checkpoint written by old code (``version=1``) may be resumed by new code
(``version=2``). Backends call :func:`migrate` on the raw dict before validating,
walking registered upgrade functions one version at a time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from spine_core.state import STATE_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]
_MIGRATIONS: dict[int, Migration] = {}


def register_migration(from_version: int, fn: Migration) -> None:
    """Register an upgrade from ``from_version`` to ``from_version + 1``."""
    _MIGRATIONS[from_version] = fn


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a raw state dict to the current ``STATE_VERSION``."""
    version = int(raw.get("version", 1))
    while version < STATE_VERSION:
        fn = _MIGRATIONS.get(version)
        if fn is None:
            raise ValueError(
                f"cannot resume: no migration from state version {version} "
                f"(current is {STATE_VERSION})"
            )
        raw = fn(raw)
        new_version = int(raw.get("version", version + 1))
        if new_version <= version:  # guard against a migration that doesn't advance
            raise ValueError(f"migration from version {version} did not advance the version")
        version = new_version
    return raw
