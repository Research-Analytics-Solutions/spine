"""Deterministic replay — record model/tool outputs, replay them exactly.

The only non-determinism in a run lives in model responses and tool results.
``Recorder`` captures both; ``Replayer`` serves them back in order so a run is
reproduced step-for-step without calling the provider or any tool (plan §10.4:
record all non-deterministic outputs; replay reads recordings).
"""

from __future__ import annotations

from typing import Any

from spine_core.messages import ModelResponse
from spine_core.middleware import StepContext, ToolContext


class Recorder:
    """Capture model responses and tool results during a live run."""

    def __init__(self) -> None:
        self.model_responses: list[ModelResponse] = []
        self.tool_results: list[Any] = []

    async def after_model(self, ctx: StepContext) -> None:
        if ctx.response is not None:
            self.model_responses.append(ctx.response.model_copy(deep=True))

    async def after_tool(self, ctx: ToolContext) -> None:
        self.tool_results.append(ctx.result)

    def recording(self) -> dict[str, Any]:
        """Serialize the recording (JSON-friendly) for storage/replay."""
        return {
            "model": [r.model_dump(mode="json") for r in self.model_responses],
            "tool": list(self.tool_results),
        }


class Replayer:
    """Serve recorded outputs in order; never calls the provider or tools.

    Accepts a :class:`Recorder` or its ``recording()`` dict. When the recording
    is exhausted it falls through to the live provider/tool (so a longer run than
    was recorded still progresses).
    """

    def __init__(self, recording: Recorder | dict[str, Any]) -> None:
        data = recording.recording() if isinstance(recording, Recorder) else recording
        self._model = [ModelResponse.model_validate(r) for r in data.get("model", [])]
        self._tool = list(data.get("tool", []))
        self._mi = 0
        self._ti = 0

    async def before_model(self, ctx: StepContext) -> None:
        if self._mi < len(self._model):
            ctx.response = self._model[self._mi].model_copy(deep=True)
            self._mi += 1

    async def before_tool(self, ctx: ToolContext) -> None:
        if self._ti < len(self._tool):
            ctx.result = self._tool[self._ti]
            ctx.skip = True
            self._ti += 1
