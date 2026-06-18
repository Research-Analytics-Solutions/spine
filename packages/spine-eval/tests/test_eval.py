"""Eval harness: scorers, aggregate report, error handling, concurrency, loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spine_core import Agent, Result, State
from spine_core.messages import Message, ModelResponse, Usage
from spine_eval import (
    Case,
    Contains,
    Dataset,
    ExactMatch,
    FunctionScorer,
    LLMJudge,
    Regex,
    evaluate,
    load_dataset,
)


class MapProvider:
    """Stateless provider: answers by input text; optionally fails on a marker."""

    def __init__(self, mapping: dict[str, str], *, fail_on: str | None = None, cost: float = 0.001):
        self.mapping = mapping
        self.fail_on = fail_on
        self.cost = cost

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        user = next(m for m in reversed(messages) if m.role.value == "user").content or ""
        if self.fail_on and self.fail_on in user:
            raise RuntimeError("boom")
        answer = self.mapping.get(user, "idk")
        return ModelResponse(
            message=Message.assistant(answer),
            usage=Usage(input_tokens=10, output_tokens=5, cost_usd=self.cost),
        )


class FixedProvider:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        return ModelResponse(message=Message.assistant(self.content), usage=Usage())


def _result(answer: str) -> Result:
    return Result(answer=answer, state=State(session_id="s"))


# -- scorers ----------------------------------------------------------------


async def test_exact_match_normalizes() -> None:
    case = Case(id="x", input="q", expected="  Four ")
    assert (await ExactMatch().score(case, _result("four"))).passed
    assert not (await ExactMatch().score(case, _result("fourish"))).passed


async def test_contains_and_regex() -> None:
    case = Case(id="x", input="q", expected="42")
    assert (await Contains().score(case, _result("the answer is 42!"))).passed
    assert not (await Contains().score(case, _result("nope"))).passed
    assert (await Regex(r"\d{2}").score(case, _result("code 42"))).passed


async def test_function_scorer() -> None:
    scorer = FunctionScorer(lambda c, r: len(r.answer or "") > 3, name="lengthy")
    assert (await scorer.score(Case(id="x", input="q"), _result("hello"))).passed
    assert not (await scorer.score(Case(id="x", input="q"), _result("hi"))).passed


async def test_llm_judge_parses_json_verdict() -> None:
    judge = LLMJudge(FixedProvider('{"score": 0.9, "pass": true, "reason": "good"}'))
    score = await judge.score(Case(id="x", input="q", expected="e"), _result("ans"))
    assert score.value == 0.9
    assert score.passed
    assert score.detail == "good"


async def test_llm_judge_handles_garbage() -> None:
    judge = LLMJudge(FixedProvider("not json at all"))
    score = await judge.score(Case(id="x", input="q"), _result("ans"))
    assert not score.passed
    assert score.value == 0.0


# -- runner / report --------------------------------------------------------


async def test_evaluate_aggregates_all_dimensions() -> None:
    dataset = Dataset(
        cases=[
            Case(id="a", input="q1", expected="4"),
            Case(id="b", input="q2", expected="zzz"),
        ]
    )
    provider = MapProvider({"q1": "the answer is 4", "q2": "nope"}, cost=0.001)
    report = await evaluate(Agent(provider), dataset, [Contains()])

    assert report.total == 2
    assert report.passed == 1
    assert report.pass_rate == 0.5
    assert report.cost_total_usd == pytest.approx(0.002)
    assert report.tokens_total == 30
    assert report.latency_avg_s >= 0.0
    assert report.scorer_means["contains"] == pytest.approx(0.5)
    assert report.error_rate == 0.0


async def test_evaluate_counts_errors_as_reliability() -> None:
    dataset = Dataset(
        cases=[
            Case(id="ok", input="good", expected="x"),
            Case(id="bad", input="explode", expected="x"),
        ]
    )
    provider = MapProvider({"good": "x here"}, fail_on="explode")
    report = await evaluate(Agent(provider), dataset, [Contains()])

    assert report.error_rate == 0.5
    bad = next(r for r in report.results if r.id == "bad")
    assert bad.error is not None
    assert bad.stopped_reason == "error"
    assert not bad.passed
    assert bad.scores == []  # not scored when the run errored


async def test_evaluate_runs_concurrently() -> None:
    cases = [Case(id=str(i), input=f"q{i}", expected=str(i)) for i in range(5)]
    provider = MapProvider({f"q{i}": f"answer {i}" for i in range(5)})
    report = await evaluate(Agent(provider), Dataset(cases=cases), [Contains()], concurrency=4)
    assert report.total == 5
    assert report.pass_rate == 1.0


# -- loader -----------------------------------------------------------------


def test_load_yaml_and_json(tmp_path: Path) -> None:
    yaml_file = tmp_path / "suite.yaml"
    yaml_file.write_text(
        "cases:\n  - id: m\n    input: 'what is 2+2?'\n    expected: '4'\n  - input: bare\n"
    )
    ds = load_dataset(yaml_file)
    assert len(ds) == 2
    assert ds.cases[0].id == "m"
    assert ds.cases[1].id == "case-1"  # default id from position

    json_file = tmp_path / "suite.json"
    json_file.write_text(json.dumps([{"id": "j", "input": "hi", "expected": "yo"}]))
    ds2 = load_dataset(json_file)
    assert ds2.cases[0].id == "j"


def test_load_rejects_bad_shape(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"nope": 1}))
    with pytest.raises(ValueError):
        load_dataset(bad)
