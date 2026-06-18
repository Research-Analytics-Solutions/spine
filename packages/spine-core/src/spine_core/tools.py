"""Tool layer — ``name + description + JSON schema + callable``.

Arguments are validated against the schema *before* the callable runs (Design
Principle: typed & validated). A tool may be a plain Python function today and a
remote MCP tool tomorrow — the kernel only sees this shape.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

import anyio
from pydantic import BaseModel, create_model

from spine_core.errors import ToolValidationError


def _args_model(func: Callable[..., Any], name: str) -> type[BaseModel]:
    """Derive a Pydantic model from a function signature for arg validation."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:  # pragma: no cover - forward refs that can't resolve
        hints = {}
    fields: dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls") or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = hints.get(pname, Any)
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[pname] = (annotation, default)
    return create_model(f"{name}_Args", **fields)


@dataclass
class Tool:
    """A validated, callable capability exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]
    approve: bool = False  # gate behind human approval (HITL) before executing
    _model: type[BaseModel] = field(repr=False, default=BaseModel)
    _is_async: bool = field(repr=False, default=False)

    @property
    def schema(self) -> dict[str, Any]:
        """Provider-facing tool declaration."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def validate(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._model(**args).model_dump()
        except Exception as exc:  # pydantic ValidationError and friends
            raise ToolValidationError(f"invalid arguments for tool '{self.name}': {exc}") from exc

    async def call(self, args: dict[str, Any]) -> Any:
        validated = self.validate(args)
        if self._is_async:
            return await self.func(**validated)
        # Run sync tools off the event loop so they never block the kernel.
        return await anyio.to_thread.run_sync(lambda: self.func(**validated))


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    approve: bool = False,
) -> Any:
    """Decorator turning a typed function into a :class:`Tool`.

    Usage::

        @tool
        async def search(query: str) -> str: ...

        @tool(approve=True)            # one flag enables HITL for this tool
        async def transfer_funds(amount: int, to: str) -> str: ...
    """

    def wrap(f: Callable[..., Any]) -> Tool:
        tool_name = name or f.__name__
        model = _args_model(f, tool_name)
        params = model.model_json_schema()
        params.pop("title", None)
        return Tool(
            name=tool_name,
            description=description or (inspect.getdoc(f) or "").strip(),
            parameters=params,
            func=f,
            approve=approve,
            _model=model,
            _is_async=inspect.iscoroutinefunction(f),
        )

    if func is not None:
        return wrap(func)
    return wrap
