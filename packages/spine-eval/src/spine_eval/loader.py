"""Load an eval dataset from YAML or JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spine_eval.models import Case, Dataset


def load_dataset(path: str | Path) -> Dataset:
    """Load a ``Dataset`` from a ``.yaml``/``.yml`` or ``.json`` file.

    Accepts either a top-level ``{"cases": [...]}`` mapping or a bare list of
    cases. Each case needs at least ``input``; ``id`` defaults to its position.
    """
    path = Path(path)
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        import yaml

        data: Any = yaml.safe_load(text)
    else:
        data = json.loads(text)

    raw_cases = data.get("cases", data) if isinstance(data, dict) else data
    if not isinstance(raw_cases, list):
        raise ValueError(f"{path}: expected a list of cases or a 'cases:' key")

    cases: list[Case] = []
    for index, item in enumerate(raw_cases):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: case #{index} is not a mapping")
        item.setdefault("id", f"case-{index}")
        cases.append(Case.model_validate(item))
    return Dataset(cases=cases)
