"""Eval data model — cases, scores, per-case results, and the aggregate report.

The report is organized along the four dimensions the plan calls out: Cost,
Latency, Efficacy, Reliability.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Case(BaseModel):
    """One evaluation case: an input and (optionally) what a good answer contains."""

    id: str
    input: str
    expected: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Dataset(BaseModel):
    cases: list[Case] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cases)


class Score(BaseModel):
    """One scorer's verdict on one case."""

    name: str
    value: float  # normalized 0..1
    passed: bool
    detail: str = ""


class CaseResult(BaseModel):
    """The outcome of running + scoring a single case."""

    id: str
    input: str
    expected: str | None = None
    answer: str | None = None
    stopped_reason: str = "final"
    error: str | None = None
    cost_usd: float = 0.0
    tokens: int = 0
    latency_s: float = 0.0
    scores: list[Score] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        if self.error is not None:
            return False
        if not self.scores:
            return self.stopped_reason == "final"
        return all(s.passed for s in self.scores)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[rank]


class EvalReport(BaseModel):
    """Aggregate metrics across all cases plus the per-case detail."""

    results: list[CaseResult] = Field(default_factory=list)
    # Efficacy
    total: int = 0
    passed: int = 0
    pass_rate: float = 0.0
    scorer_means: dict[str, float] = Field(default_factory=dict)
    # Cost
    cost_total_usd: float = 0.0
    cost_avg_usd: float = 0.0
    tokens_total: int = 0
    # Latency
    latency_avg_s: float = 0.0
    latency_p95_s: float = 0.0
    # Reliability
    error_rate: float = 0.0
    stop_reasons: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_results(cls, results: list[CaseResult]) -> EvalReport:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        latencies = [r.latency_s for r in results]
        errors = sum(1 for r in results if r.error is not None)

        scorer_values: dict[str, list[float]] = {}
        for result in results:
            for score in result.scores:
                scorer_values.setdefault(score.name, []).append(score.value)

        stop_reasons: dict[str, int] = {}
        for result in results:
            stop_reasons[result.stopped_reason] = stop_reasons.get(result.stopped_reason, 0) + 1

        cost_total = sum(r.cost_usd for r in results)
        return cls(
            results=results,
            total=total,
            passed=passed,
            pass_rate=(passed / total) if total else 0.0,
            scorer_means={k: sum(v) / len(v) for k, v in scorer_values.items()},
            cost_total_usd=cost_total,
            cost_avg_usd=(cost_total / total) if total else 0.0,
            tokens_total=sum(r.tokens for r in results),
            latency_avg_s=(sum(latencies) / total) if total else 0.0,
            latency_p95_s=_percentile(latencies, 95),
            error_rate=(errors / total) if total else 0.0,
            stop_reasons=stop_reasons,
        )
