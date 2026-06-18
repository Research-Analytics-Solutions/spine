"""Spine storage backends.

Importing the package registers the ``sqlite`` checkpoint backend by name, so
``spine.toml`` ``checkpoint = "sqlite"`` resolves.
"""

from __future__ import annotations

from spine_backends.memory import InMemoryVectorMemory, default_embed
from spine_backends.migrations import register_migration
from spine_backends.postgres import PostgresCheckpoint
from spine_backends.redis import RedisCheckpoint
from spine_backends.sqlite import SQLiteCheckpoint

__all__ = [
    "InMemoryVectorMemory",
    "PostgresCheckpoint",
    "RedisCheckpoint",
    "SQLiteCheckpoint",
    "default_embed",
    "register_migration",
]
