import json
from pathlib import Path

from metrics import score_cases


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
