# Evaluation

`spine-eval` runs an agent against a dataset of cases, scores with pluggable
scorers, and reports along **Cost / Latency / Efficacy / Reliability** — the
lab-to-prod gap, measured.

## A dataset

`evals/smoke.yaml`:

```yaml
cases:
  - id: math
    input: "what is 2 + 2?"
    expected: "4"
  - id: capital
    input: "capital of France?"
    expected: "Paris"
```

## Run it

```python
from spine_eval import evaluate, load_dataset, Contains

dataset = load_dataset("evals/smoke.yaml")
report = await evaluate(agent, dataset, [Contains()], concurrency=4)

print(f"pass {report.pass_rate:.0%}  cost ${report.cost_total_usd:.4f}  "
      f"p95 {report.latency_p95_s:.2f}s  errors {report.error_rate:.0%}")
```

Each case runs in a fresh session; `concurrency` bounds parallel cases. A crash is
a failed case, not a failed eval.

## Scorers

| Scorer | Checks |
|---|---|
| `ExactMatch` | normalized equality with `expected` |
| `Contains` | `expected` is a substring of the answer |
| `Regex` | answer matches a pattern |
| `FunctionScorer` | any `(case, result) -> bool \| float` |
| `LLMJudge` | grade with another model (JSON verdict) |

```python
from spine_eval import LLMJudge, FunctionScorer

scorers = [
    LLMJudge(judge_provider),
    FunctionScorer(lambda c, r: len(r.answer or "") < 200, name="concise"),
]
```

## From the CLI

```bash
spine eval evals/smoke.yaml --scorer contains
```

Exits non-zero on any failure — drop it straight into CI.
