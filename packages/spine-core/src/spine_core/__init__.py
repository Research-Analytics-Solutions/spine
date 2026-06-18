"""Spine core — the tiny, protocol-native kernel for production AI agents.

Public API. Everything else (providers, MCP, OTel, backends, CLI) plugs into
these primitives without editing the kernel.
"""

from __future__ import annotations

from spine_core.agent import Agent
from spine_core.checkpoint import CheckpointStore, InMemoryCheckpointStore
from spine_core.control import StopRun
from spine_core.errors import (
    ProviderError,
    ResumeError,
    SpineError,
    ToolError,
    ToolValidationError,
)
from spine_core.guards import Guards
from spine_core.interrupt import Interrupt
from spine_core.memory import Embedder, Memory, MemoryHit, MemoryRecord
from spine_core.messages import (
    Message,
    ModelResponse,
    Role,
    ToolCall,
    Usage,
    image_part,
    text_part,
)
from spine_core.middleware import (
    ErrorAction,
    Middleware,
    MiddlewareChain,
    StepContext,
    ToolContext,
)
from spine_core.provider import (
    Provider,
    StreamChunk,
    StreamingProvider,
    register_provider,
    resolve_provider,
)
from spine_core.registry import (
    list_checkpoints,
    list_memories,
    list_middleware,
    register_checkpoint,
    register_memory,
    register_middleware,
    resolve_checkpoint,
    resolve_memory,
    resolve_middleware,
)
from spine_core.result import Result, StopReason
from spine_core.state import PendingApproval, RunStatus, State
from spine_core.tools import Tool, raw_tool, tool
from spine_core.trace import EventType, TraceEvent, Tracer

__version__ = "0.1.0"  # x-release-please-version

__all__ = [
    "Agent",
    "CheckpointStore",
    "InMemoryCheckpointStore",
    "ErrorAction",
    "EventType",
    "Embedder",
    "Guards",
    "Interrupt",
    "Memory",
    "MemoryHit",
    "MemoryRecord",
    "Message",
    "Middleware",
    "MiddlewareChain",
    "ModelResponse",
    "PendingApproval",
    "Provider",
    "ProviderError",
    "Result",
    "ResumeError",
    "Role",
    "RunStatus",
    "SpineError",
    "State",
    "StepContext",
    "StopReason",
    "StopRun",
    "StreamChunk",
    "StreamingProvider",
    "Tool",
    "ToolCall",
    "ToolContext",
    "ToolError",
    "ToolValidationError",
    "TraceEvent",
    "Tracer",
    "Usage",
    "list_checkpoints",
    "list_memories",
    "list_middleware",
    "register_checkpoint",
    "register_memory",
    "register_middleware",
    "register_provider",
    "resolve_checkpoint",
    "resolve_memory",
    "resolve_middleware",
    "resolve_provider",
    "raw_tool",
    "text_part",
    "image_part",
    "tool",
    "__version__",
]
