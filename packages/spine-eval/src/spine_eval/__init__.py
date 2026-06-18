"""Spine eval harness — run an agent over a dataset, score, and report.

```python
from spine_eval import evaluate, load_dataset, Contains

report = await evaluate(agent, load_dataset("evals/smoke.yaml"), [Contains()])
print(report.pass_rate, report.cost_total_usd)
```

Reports across the four dimensions the plan calls out — Cost, Latency, Efficacy,
Reliability — to target the lab-to-prod gap directly.
"""

from __future__ import annotations

from spine_eval.loader import load_dataset
from spine_eval.models import Case, CaseResult, Dataset, EvalReport, Score
from spine_eval.runner import evaluate
from spine_eval.scorers import (
    Contains,
    ExactMatch,
    FunctionScorer,
    LLMJudge,
    Regex,
    Scorer,
)

__all__ = [
    "Case",
    "CaseResult",
    "Contains",
    "Dataset",
    "EvalReport",
    "ExactMatch",
    "FunctionScorer",
    "LLMJudge",
    "Regex",
    "Score",
    "Scorer",
    "evaluate",
    "load_dataset",
]
