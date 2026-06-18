"""Spine storage backends.

Importing the package registers the ``sqlite`` checkpoint backend by name, so
``spine.toml`` ``checkpoint = "sqlite"`` resolves.
"""

from __future__ import annotations

from spine_backends.embeddings import HashEmbedder, OpenAIEmbedder
from spine_backends.memory import BufferMemory, InMemoryVectorMemory
from spine_backends.migrations import register_migration
from spine_backends.pgvector import PgVectorMemory
from spine_backends.postgres import PostgresCheckpoint
from spine_backends.redis import RedisCheckpoint
from spine_backends.sqlite import SQLiteCheckpoint

__all__ = [
    "BufferMemory",
    "HashEmbedder",
    "InMemoryVectorMemory",
    "OpenAIEmbedder",
    "PgVectorMemory",
    "PostgresCheckpoint",
    "RedisCheckpoint",
    "SQLiteCheckpoint",
    "register_migration",
]
