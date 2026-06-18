"""Provider protocol + string registry.

A provider is a one-method object: ``complete(messages, tools) -> ModelResponse``.
The router (a later middleware/provider) wraps an ordered list and applies
fallback/cost policies — it satisfies the same protocol, so the kernel is
oblivious to whether it's talking to one model or many.

``Agent("anthropic:claude-sonnet-4-6")`` resolves a ``scheme:model`` string to a
provider via this registry, which real adapters populate through plugin entry
points. Discovery stays lazy: an unused provider costs nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from spine_core.errors import ProviderError
from spine_core.messages import Message, ModelResponse


@runtime_checkable
class Provider(Protocol):
    """Anything that can turn messages + tool schemas into a response."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse: ...


class StreamChunk(BaseModel):
    """One streamed piece. ``delta`` is incremental text; the final chunk carries
    the assembled ``response``."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    delta: str = ""
    response: ModelResponse | None = None


@runtime_checkable
class StreamingProvider(Protocol):
    """A provider that can stream token deltas as well as a final response."""

    def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]: ...


# scheme -> factory(model_name) -> Provider
ProviderFactory = Callable[[str], Provider]
_REGISTRY: dict[str, ProviderFactory] = {}


def register_provider(scheme: str, factory: ProviderFactory) -> None:
    """Register a provider factory under a ``scheme`` (e.g. ``"anthropic"``)."""
    _REGISTRY[scheme] = factory


def _load_provider_plugin(scheme: str) -> None:
    """Lazily import the installed plugin whose entry-point name is ``scheme``.

    Lets ``Agent("openai:...")`` work after ``pip install spinekit[openai]``
    without an explicit ``import spine_providers`` — the adapter self-registers
    on import.
    """
    import contextlib
    from importlib.metadata import entry_points

    for ep in entry_points(group="spine.plugins"):
        if ep.name == scheme:
            # A missing optional dep just means this adapter isn't usable here.
            with contextlib.suppress(Exception):
                ep.load()


def resolve_provider(spec: str | Provider) -> Provider:
    """Resolve a provider instance or a ``"scheme:model"`` string."""
    if not isinstance(spec, str):
        if isinstance(spec, Provider):
            return spec
        raise ProviderError(f"object {spec!r} does not implement the Provider protocol")
    scheme, _, model = spec.partition(":")
    factory = _REGISTRY.get(scheme)
    if factory is None:
        _load_provider_plugin(scheme)  # try installed adapters before giving up
        factory = _REGISTRY.get(scheme)
    if factory is None:
        known = ", ".join(sorted(_REGISTRY)) or "<none installed>"
        raise ProviderError(
            f"no provider registered for scheme '{scheme}'. Installed: {known}. "
            f"Install an adapter (e.g. `pip install spinekit[{scheme}]`) or pass a "
            f"Provider instance."
        )
    return factory(model)
