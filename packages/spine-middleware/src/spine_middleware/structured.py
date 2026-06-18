"""StructuredOutput middleware — schema-enforced final answer with repair loop."""

from __future__ import annotations

from pydantic import BaseModel

from spine_core.control import StopRun
from spine_core.messages import Message
from spine_core.middleware import StepContext
from spine_core.result import StopReason

_PENDING = "_structured_pending_error"
_REPAIRS = "_structured_repairs"


def _extract_json(content: str) -> str:
    """Pull a JSON object out of a model answer, tolerating ``` fences."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


class StructuredOutput:
    """Validate the final answer against a Pydantic schema, repairing on failure.

    On an invalid final answer it feeds the validation error back as a new turn
    (capped at ``max_repairs``) via ``force_continue``; on success the parsed
    object is stashed in ``state.scratch[key]``; when repairs are exhausted the
    run fails loud with :attr:`StopReason.ERROR`.
    """

    def __init__(
        self,
        schema: type[BaseModel],
        *,
        max_repairs: int = 2,
        key: str = "structured_output",
    ) -> None:
        self.schema = schema
        self.max_repairs = max_repairs
        self.key = key

    async def before_model(self, ctx: StepContext) -> None:
        error = ctx.state.scratch.pop(_PENDING, None)
        if error:
            ctx.state.add_message(
                Message.user(
                    f"Your previous reply was not valid for the required schema "
                    f"'{self.schema.__name__}'. Error: {error}. "
                    f"Reply with ONLY the corrected JSON object."
                )
            )

    async def after_model(self, ctx: StepContext) -> None:
        if ctx.response is None or ctx.response.message.tool_calls:
            return  # only police plain final answers, not tool-using turns
        content = ctx.response.message.content or ""
        try:
            obj = self.schema.model_validate_json(_extract_json(content))
        except Exception as exc:  # noqa: BLE001 - validation/parse failure
            repairs = ctx.state.scratch.get(_REPAIRS, 0)
            if repairs >= self.max_repairs:
                raise StopRun(
                    StopReason.ERROR,
                    f"structured output invalid after {repairs} repair attempts: {exc}",
                ) from exc
            ctx.state.scratch[_REPAIRS] = repairs + 1
            ctx.state.scratch[_PENDING] = str(exc)
            ctx.force_continue = True
            return
        ctx.state.scratch[self.key] = obj.model_dump()
        ctx.state.scratch.pop(_REPAIRS, None)
