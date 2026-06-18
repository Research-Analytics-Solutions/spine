"""Spine V1 middleware suite.

Reliability and shaping middlewares built entirely on the kernel's hook points —
no kernel edits. Importing this package registers the config-addressable ones
(``Retry``, ``ModelFallback``, ``LoopGuard``, ``CostTracking``, ``Compaction``)
by name so ``spine.toml`` chains resolve them.
"""

from __future__ import annotations

from spine_core.registry import register_middleware
from spine_middleware.compaction import Compaction
from spine_middleware.cost import CostTracking
from spine_middleware.fallback import ModelFallback
from spine_middleware.loopguard import LoopGuard
from spine_middleware.retry import Retry
from spine_middleware.structured import StructuredOutput

__all__ = [
    "Compaction",
    "CostTracking",
    "LoopGuard",
    "ModelFallback",
    "Retry",
    "StructuredOutput",
]


def register() -> None:
    """Register middlewares under their class name in the core registry."""
    register_middleware("Retry", Retry)
    register_middleware("ModelFallback", ModelFallback)
    register_middleware("LoopGuard", LoopGuard)
    register_middleware("CostTracking", CostTracking)
    register_middleware("Compaction", Compaction)
    # StructuredOutput needs a schema type, so it is used from code, not config.


register()
