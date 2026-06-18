# spine-eval

Run an agent against a dataset of cases, score with pluggable scorers, and
report along **Cost / Latency / Efficacy / Reliability** — the lab-to-prod gap,
measured.

```python
from spine_eval import evaluate, load_dataset, Contains, LLMJudge

dataset = load_dataset("evals/smoke.yaml")
report = await evaluate(agent, dataset, [Contains()], concurrency=4)

print(f"pass {report.pass_rate:.0%}  cost ${report.cost_total_usd:.4f}  "
      f"p95 {report.latency_p95_s:.2f}s  errors {report.error_rate:.0%}")
```

Dataset (`evals/smoke.yaml`):

```yaml
cases:
  - id: math
    input: "what is 2 + 2?"
    expected: "4"
```

Scorers: `ExactMatch`, `Contains`, `Regex`, `FunctionScorer` (any callable), and
`LLMJudge` (grade with another model). Each case runs in a fresh session;
`concurrency` bounds parallel cases. Run from the CLI with `spine eval <suite>`.
