"""Spine V1 middleware suite.

Reliability and shaping middlewares built entirely on the kernel's hook points —
no kernel edits. Importing this package registers the config-addressable ones
(``Retry``, ``ModelFallback``, ``LoopGuard``, ``CostTracking``, ``Compaction``)
by name so ``spine.toml`` chains resolve them.
"""

from __future__ import annotations

from spine_core.registry import register_middleware
from spine_middleware.cache import Cache
from spine_middleware.compaction import Compaction
from spine_middleware.cost import CostTracking
from spine_middleware.fallback import ModelFallback
from spine_middleware.guardrails import ContentPolicy, PIIRedaction, PromptInjectionScreen
from spine_middleware.loopguard import LoopGuard
from spine_middleware.memory import MemoryRecall
from spine_middleware.reliability import CircuitBreaker, Idempotency, RateLimit
from spine_middleware.replay import Recorder, Replayer
from spine_middleware.retry import Retry
from spine_middleware.structured import StructuredOutput
from spine_middleware.tooling import ToolOutputTruncation, ToolTimeout

__all__ = [
    "Cache",
    "CircuitBreaker",
    "Compaction",
    "ContentPolicy",
    "CostTracking",
    "Idempotency",
    "LoopGuard",
    "MemoryRecall",
    "ModelFallback",
    "PIIRedaction",
    "PromptInjectionScreen",
    "RateLimit",
    "Recorder",
    "Replayer",
    "Retry",
    "StructuredOutput",
    "ToolOutputTruncation",
    "ToolTimeout",
]


def register() -> None:
    """Register middlewares under their class name in the core registry."""
    register_middleware("Retry", Retry)
    register_middleware("ModelFallback", ModelFallback)
    register_middleware("LoopGuard", LoopGuard)
    register_middleware("CostTracking", CostTracking)
    register_middleware("Compaction", Compaction)
    register_middleware("Cache", Cache)
    register_middleware("PIIRedaction", PIIRedaction)
    register_middleware("PromptInjectionScreen", PromptInjectionScreen)
    register_middleware("ContentPolicy", ContentPolicy)
    register_middleware("CircuitBreaker", CircuitBreaker)
    register_middleware("RateLimit", RateLimit)
    register_middleware("Idempotency", Idempotency)
    register_middleware("ToolTimeout", ToolTimeout)
    register_middleware("ToolOutputTruncation", ToolOutputTruncation)
    # StructuredOutput needs a schema type, so it is used from code, not config.


register()
