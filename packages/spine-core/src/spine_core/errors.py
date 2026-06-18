"""Kernel exception hierarchy."""

from __future__ import annotations


class SpineError(Exception):
    """Base class for all Spine errors."""


class ProviderError(SpineError):
    """A model provider failed to produce a response."""


class ToolError(SpineError):
    """A tool was missing, mis-declared, or failed to execute."""


class ToolValidationError(ToolError):
    """Tool arguments did not satisfy the tool's schema."""


class ResumeError(SpineError):
    """A resume token did not map to a resumable run."""
