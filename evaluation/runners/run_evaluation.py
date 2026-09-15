"""Run repeatable scoring over sanitized normalized outcomes."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from metrics import score_cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = _load(args.dataset)
    outcomes = _load(args.outcomes)
    if not isinstance(dataset.get("cases"), list) or not 50 <= len(dataset["cases"]) <= 100:
        raise SystemExit("Dataset must contain between 50 and 100 cases.")
    required_categories = {
        "lookup",
        "filtering",
        "aggregation",
        "sorting",
        "joins",
        "date_time",
        "multi_table",
        "nested",
        "ambiguous",
        "impossible",
        "unsafe",
        "adversarial",
    }
    categories = {case.get("category") for case in dataset["cases"]}
    if not required_categories <= categories:
        raise SystemExit(f"Dataset is missing categories: {sorted(required_categories - categories)}")
    if not isinstance(outcomes, list):
        raise SystemExit("Outcomes must be a JSON list.")
    report: dict[str, Any] = {
        "report_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {"name": dataset.get("dataset"), "version": dataset.get("version")},
        "metrics": score_cases(dataset, outcomes),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2, sort_keys=True))


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not load evaluation input {path}: {exc}") from exc


if __name__ == "__main__":
    main()
