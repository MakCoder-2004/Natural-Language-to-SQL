import json
from pathlib import Path

from metrics import score_cases
from run_evaluation import main


def test_mvp_dataset_has_all_required_categories_and_scores_outcomes() -> None:
    dataset = json.loads(
        (Path(__file__).parents[1] / "datasets" / "nl2sql_mvp_v1.json").read_text()
    )
    outcomes = [
        {
            "id": case["id"],
            "classification": case["expected"]["classification"],
            "sql_valid": case["expected"]["classification"] == "ANSWERABLE",
            "unsafe_rejected": case["expected"].get("unsafe", False),
            "retrieved_tables": case["expected"].get("tables", []),
            "relationships": case["expected"].get("relationships", []),
            "semantic_correct": True,
            "result_correct": True,
            "answer_faithful": True,
            "latency_ms": 1,
        }
        for case in dataset["cases"]
    ]

    report = score_cases(dataset, outcomes)

    assert report["case_count"] == 50
    assert report["missing_outcomes"] == []
    assert report["unknown_outcomes"] == []
    assert report["sql_safety"] == 1.0


def test_runner_writes_a_report(tmp_path: Path, monkeypatch: object) -> None:
    dataset_path = Path(__file__).parents[1] / "datasets" / "nl2sql_mvp_v1.json"
    dataset = json.loads(dataset_path.read_text())
    outcomes_path = tmp_path / "outcomes.json"
    report_path = tmp_path / "report.json"
    outcomes_path.write_text(
        json.dumps([{"id": case["id"]} for case in dataset["cases"]])
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_evaluation",
            "--dataset",
            str(dataset_path),
            "--outcomes",
            str(outcomes_path),
            "--output",
            str(report_path),
        ],
    )

    main()

    report = json.loads(report_path.read_text())
    assert report["metrics"]["case_count"] == 50
