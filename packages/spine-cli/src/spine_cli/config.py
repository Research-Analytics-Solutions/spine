"""``spine.toml`` loader.

An agent's full behavior is reproducible from version control: model, guards,
middleware order, and backends are declared here. Secrets are never inlined —
``${ENV_VAR}`` references are interpolated from the environment at load time.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from spine_core import Guards

_ENV_REF = re.compile(r"\$\{([^}]+)\}")

CONFIG_FILENAME = "spine.toml"


class MiddlewareConfig(BaseModel):
    chain: list[str] = Field(default_factory=list)


class BackendsConfig(BaseModel):
    checkpoint: str | None = None
    memory: str | None = None


class SpineConfig(BaseModel):
    default_model: str = "anthropic:claude-sonnet-4-6"
    system: str | None = None
    guards: Guards = Field(default_factory=Guards)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    plugins: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ConfigError(Exception):
    """``spine.toml`` is missing, malformed, or references an unset env var."""


def _interpolate(value: Any) -> Any:
    """Recursively replace ``${VAR}`` with the environment value."""
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            resolved = os.environ.get(name)
            if resolved is None:
                raise ConfigError(
                    f"environment variable '{name}' referenced in spine.toml is unset"
                )
            return resolved

        return _ENV_REF.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def find_config(start: Path) -> Path | None:
    """Search ``start`` and its parents for ``spine.toml``."""
    start = start.resolve()
    for directory in (start, *start.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Path) -> SpineConfig:
    """Load and validate ``spine.toml`` at ``path`` (a file or its directory)."""
    config_path = path if path.is_file() else path / CONFIG_FILENAME
    if not config_path.is_file():
        raise ConfigError(f"no {CONFIG_FILENAME} found at {config_path}")
    try:
        raw = tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{config_path} is not valid TOML: {exc}") from exc

    section = _interpolate(raw.get("spine", {}))
    try:
        return SpineConfig.model_validate(section)
    except Exception as exc:  # pydantic ValidationError
        raise ConfigError(f"invalid [spine] config in {config_path}: {exc}") from exc
