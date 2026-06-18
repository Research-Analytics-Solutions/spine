"""Spine model provider adapters.

Importing this package eagerly registers the bundled schemes (e.g.
``anthropic:``) with the core provider registry, so
``Agent("anthropic:claude-sonnet-4-6")`` resolves once ``spine-providers`` is
installed. Discovery via plugin entry points is also declared for the CLI.
"""

from __future__ import annotations

from spine_providers.anthropic import AnthropicProvider
from spine_providers.anthropic import register as _register_anthropic

_register_anthropic()

__all__ = ["AnthropicProvider"]
