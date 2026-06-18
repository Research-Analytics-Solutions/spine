"""Run an agent across a dataset and score each case, with bounded concurrency."""

from __future__ import annotations

import time

import anyio

from spine_core import Agent
from spine_eval.models import Case, CaseResult, Dataset, EvalReport
from spine_eval.scorers import Scorer


async def _run_case(agent: Agent, case: Case, scorers: list[Scorer]) -> CaseResult:
    started = time.perf_counter()
    try:
        result = await agent.run(case.input)
    except Exception as exc:  # noqa: BLE001 - a crash is a failed case, not a failed eval
        return CaseResult(
            id=case.id,
            input=case.input,
            expected=case.expected,
            error=f"{type(exc).__name__}: {exc}",
            stopped_reason="error",
            latency_s=time.perf_counter() - started,
        )
    latency = time.perf_counter() - started

    record = CaseResult(
        id=case.id,
        input=case.input,
        expected=case.expected,
        answer=result.answer,
        stopped_reason=result.stopped_reason.value,
        error=result.error,
        cost_usd=result.usage.cost_usd,
        tokens=result.usage.total_tokens,
        latency_s=latency,
    )
    if record.error is None:
        for scorer in scorers:
            record.scores.append(await scorer.score(case, result))
    return record


async def evaluate(
    agent: Agent,
    dataset: Dataset,
    scorers: list[Scorer] | None = None,
    *,
    concurrency: int = 1,
) -> EvalReport:
    """Evaluate ``agent`` over ``dataset``; each case runs in a fresh session.

    ``concurrency`` bounds simultaneous cases. Keep it at 1 when the provider or
    a scorer is not safe to call concurrently.
    """
    scorers = scorers or []
    cases = dataset.cases
    results: list[CaseResult | None] = [None] * len(cases)
    limiter = anyio.CapacityLimiter(max(1, concurrency))

    async def worker(index: int, case: Case) -> None:
        async with limiter:
            results[index] = await _run_case(agent, case, scorers)

    async with anyio.create_task_group() as tg:
        for index, case in enumerate(cases):
            tg.start_soon(worker, index, case)

    return EvalReport.from_results([r for r in results if r is not None])
