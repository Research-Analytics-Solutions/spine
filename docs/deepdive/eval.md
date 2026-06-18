# Deep dive: evaluation

A complete walkthrough of `spine-eval` — from a dataset to a CI gate.

## The pieces

- **`Case`** — one test: `id`, `input`, optional `expected`, optional `metadata`.
- **`Dataset`** — a list of cases (`load_dataset` reads YAML/JSON).
- **`Scorer`** — `async def score(case, result) -> Score`.
- **`evaluate(agent, dataset, scorers=None, *, concurrency=1) -> EvalReport`**.
- **`EvalReport`** — aggregates across **Cost / Latency / Efficacy / Reliability**.

## 1. Write a dataset

`evals/support.yaml`:

```yaml
cases:
  - id: refund-policy
    input: "What is our refund window?"
    expected: "30 days"
  - id: greeting
    input: "hi"
    expected: "hello"
  - id: math
    input: "what is 12 * 12?"
    expected: "144"
```

A bare list works too; `id` defaults to position.

## 2. Run it

```python
from spine_eval import evaluate, load_dataset, Contains

dataset = load_dataset("evals/support.yaml")
report = await evaluate(agent, dataset, [Contains()], concurrency=4)
```

Each case runs in a **fresh session** (no cross-case leakage); `concurrency` bounds
parallel cases. A case that crashes is a failed case, not a failed eval.

## 3. Read the report

```python
print(f"pass rate : {report.pass_rate:.0%} ({report.passed}/{report.total})")
print(f"error rate: {report.error_rate:.0%}")
print(f"cost      : ${report.cost_total_usd:.4f} (avg ${report.cost_avg_usd:.5f})")
print(f"latency   : avg {report.latency_avg_s:.2f}s · p95 {report.latency_p95_s:.2f}s")
print(f"by scorer : {report.scorer_means}")
print(f"stop mix  : {report.stop_reasons}")

for r in report.results:
    print(r.id, "PASS" if r.passed else "FAIL", r.scores)
```

The four dimensions map to the lab-to-prod gap: **Efficacy** (pass rate, scorer
means), **Cost** (total/avg), **Latency** (avg/p95), **Reliability** (error rate,
stop-reason mix).

## 4. Scorers

| Scorer | Use |
|---|---|
| `ExactMatch(strip=, casefold=)` | normalized equality |
| `Contains(casefold=)` | `expected` is a substring |
| `Regex(pattern, flags=)` | answer matches a pattern |
| `FunctionScorer(fn, name=, threshold=)` | any `(case, result) -> bool \| float` |
| `LLMJudge(provider, threshold=)` | grade with another model |

### A custom scorer

```python
from spine_eval import FunctionScorer

concise = FunctionScorer(
    lambda case, result: len(result.answer or "") <= 280,
    name="concise",
)
```

`FunctionScorer` accepts sync or async callables, returning `bool` or a `float`
score (compared to `threshold`).

### LLM-as-judge

```python
from spine_eval import LLMJudge
from spine_providers import OpenAIProvider

judge = LLMJudge(OpenAIProvider("gpt-4o-mini"), threshold=0.5)
report = await evaluate(agent, dataset, [judge])
```

The judge is asked for a JSON verdict (`{"score", "pass", "reason"}`); an
unparseable reply scores 0 (fails safe).

### Stack scorers

```python
report = await evaluate(agent, dataset, [Contains(), concise, judge])
# a case passes only if ALL its scorers pass; scorer_means has each one
```

## 5. From the CLI / in CI

```bash
spine eval evals/support.yaml --scorer contains
```

Exits **non-zero** on any failure — drop it straight into a CI step:

```yaml
- run: uv run spine eval evals/support.yaml
```

## 6. Offline, deterministic eval

Pair eval with [deterministic replay](../concepts/observability.md#deterministic-replay):
record real runs once, then eval the `Replayer` in CI — same scores, no API cost.
