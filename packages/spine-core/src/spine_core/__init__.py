"""Spine core — the tiny, protocol-native kernel for production AI agents.

Public API. Everything else (providers, MCP, OTel, backends, CLI) plugs into
these primitives without editing the kernel.
"""

from __future__ import annotations

from spine_core.agent import Agent
from spine_core.checkpoint import CheckpointStore, InMemoryCheckpointStore
from spine_core.errors import (
    ProviderError,
    ResumeError,
    SpineError,
    ToolError,
    ToolValidationError,
)
from spine_core.guards import Guards
from spine_core.interrupt import Interrupt
from spine_core.messages import Message, ModelResponse, Role, ToolCall, Usage
from spine_core.middleware import (
    ErrorAction,
    Middleware,
    MiddlewareChain,
    StepContext,
    ToolContext,
)
from spine_core.provider import Provider, register_provider, resolve_provider
from spine_core.result import Result, StopReason
from spine_core.state import PendingApproval, RunStatus, State
from spine_core.tools import Tool, tool
from spine_core.trace import EventType, TraceEvent, Tracer

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "CheckpointStore",
    "InMemoryCheckpointStore",
    "ErrorAction",
    "EventType",
    "Guards",
    "Interrupt",
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
    "Tool",
    "ToolCall",
    "ToolContext",
    "ToolError",
    "ToolValidationError",
    "TraceEvent",
    "Tracer",
    "Usage",
    "register_provider",
    "resolve_provider",
    "tool",
    "__version__",
]
