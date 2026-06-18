"""Plugin discovery via ``importlib.metadata`` entry points.

Plugins are ordinary installed packages registered under the ``spine.plugins``
group — the same mechanism pytest and Flask use. Loading an entry point imports
its module, which self-registers (e.g. a provider scheme). Discovery is lazy:
nothing is loaded until asked for.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points

GROUP = "spine.plugins"

# Packages we publish; everything else is flagged third-party (enterprise gate).
_FIRST_PARTY = {"spine_core", "spine_providers", "spine_cli", "spine_mcp", "spine_otel"}


@dataclass
class PluginInfo:
    name: str
    value: str  # "module:attr" target
    loaded: bool
    error: str | None = None

    @property
    def module(self) -> str:
        return self.value.split(":", 1)[0]

    @property
    def first_party(self) -> bool:
        return self.module.split(".", 1)[0] in _FIRST_PARTY


def discover() -> list[PluginInfo]:
    """Enumerate installed Spine plugins without importing them."""
    return [
        PluginInfo(name=ep.name, value=ep.value, loaded=False) for ep in entry_points(group=GROUP)
    ]


def load_all() -> list[PluginInfo]:
    """Import every installed plugin so its schemes/backends register."""
    results: list[PluginInfo] = []
    for ep in entry_points(group=GROUP):
        info = PluginInfo(name=ep.name, value=ep.value, loaded=False)
        try:
            ep.load()
            info.loaded = True
        except Exception as exc:  # noqa: BLE001 - report, don't crash the CLI
            info.error = str(exc)
        results.append(info)
    return results
