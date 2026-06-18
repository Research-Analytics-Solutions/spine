"""Pluggable scorers — exact match, substring, regex, custom, LLM-as-judge."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from spine_core import Result
from spine_core.messages import Message
from spine_core.provider import Provider
from spine_eval.models import Case, Score


@runtime_checkable
class Scorer(Protocol):
    name: str

    async def score(self, case: Case, result: Result) -> Score: ...


def _normalize(text: str | None, *, strip: bool = True, casefold: bool = True) -> str:
    text = text or ""
    if strip:
        text = text.strip()
    if casefold:
        text = text.casefold()
    return text


class ExactMatch:
    """Answer must equal ``case.expected`` (normalized)."""

    name = "exact_match"

    def __init__(self, *, strip: bool = True, casefold: bool = True) -> None:
        self.strip = strip
        self.casefold = casefold

    async def score(self, case: Case, result: Result) -> Score:
        answer = _normalize(result.answer, strip=self.strip, casefold=self.casefold)
        expected = _normalize(case.expected, strip=self.strip, casefold=self.casefold)
        passed = answer == expected
        return Score(name=self.name, value=1.0 if passed else 0.0, passed=passed)


class Contains:
    """``case.expected`` must appear as a substring of the answer (normalized)."""

    name = "contains"

    def __init__(self, *, casefold: bool = True) -> None:
        self.casefold = casefold

    async def score(self, case: Case, result: Result) -> Score:
        answer = _normalize(result.answer, strip=False, casefold=self.casefold)
        expected = _normalize(case.expected, strip=True, casefold=self.casefold)
        passed = bool(expected) and expected in answer
        return Score(name=self.name, value=1.0 if passed else 0.0, passed=passed)


class Regex:
    """The answer must match a regular expression."""

    name = "regex"

    def __init__(self, pattern: str, *, flags: int = 0) -> None:
        self._re = re.compile(pattern, flags)

    async def score(self, case: Case, result: Result) -> Score:
        passed = bool(self._re.search(result.answer or ""))
        return Score(name=self.name, value=1.0 if passed else 0.0, passed=passed)


class FunctionScorer:
    """Wrap a user callable ``(case, result) -> bool | float`` as a scorer."""

    def __init__(
        self,
        fn: Callable[[Case, Result], bool | float | Awaitable[bool | float]],
        *,
        name: str = "custom",
        threshold: float = 0.5,
    ) -> None:
        self.fn = fn
        self.name = name
        self.threshold = threshold

    async def score(self, case: Case, result: Result) -> Score:
        import inspect

        outcome = self.fn(case, result)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        value = float(outcome)
        return Score(name=self.name, value=value, passed=value >= self.threshold)


_JUDGE_PROMPT = (
    "You are grading an AI answer. Question: {input}\n"
    "Reference (expected): {expected}\n"
    "Answer to grade: {answer}\n"
    'Respond with ONLY JSON: {{"score": <0..1 float>, "pass": <true|false>, '
    '"reason": "<short>"}}.'
)


class LLMJudge:
    """Grade the answer with another model (LLM-as-judge)."""

    name = "llm_judge"

    def __init__(self, provider: Provider, *, threshold: float = 0.5) -> None:
        self.provider = provider
        self.threshold = threshold

    async def score(self, case: Case, result: Result) -> Score:
        prompt = _JUDGE_PROMPT.format(
            input=case.input, expected=case.expected or "(none)", answer=result.answer or ""
        )
        response = await self.provider.complete([Message.user(prompt)])
        content = response.message.content or "{}"
        try:
            start, end = content.find("{"), content.rfind("}")
            data = json.loads(content[start : end + 1])
            value = float(data.get("score", 0.0))
            passed = bool(data.get("pass", value >= self.threshold))
            detail = str(data.get("reason", ""))
        except (ValueError, KeyError, TypeError):
            return Score(name=self.name, value=0.0, passed=False, detail="unparseable judge reply")
        return Score(name=self.name, value=value, passed=passed, detail=detail)
