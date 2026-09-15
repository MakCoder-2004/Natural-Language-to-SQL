"""Deterministic metric calculations for normalized evaluation outcomes."""

from __future__ import annotations

from collections import Counter
from typing import Any


def score_cases(dataset: dict[str, Any], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Score outcomes without inspecting raw prompts, SQL, or database rows."""

    expected = {case["id"]: case for case in dataset["cases"]}
    by_id = {outcome["id"]: outcome for outcome in outcomes}
    answerable = [case for case in dataset["cases"] if case["expected"]["classification"] == "ANSWERABLE"]
    unsafe = [case for case in dataset["cases"] if case["expected"].get("unsafe", False)]

    def fraction(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    sql_cases = [case for case in answerable if case["id"] in by_id]
    safe_cases = [case for case in unsafe if case["id"] in by_id]
    valid = sum(bool(by_id[case["id"]].get("sql_valid")) for case in sql_cases)
    safe = sum(bool(by_id[case["id"]].get("unsafe_rejected")) for case in safe_cases)
    clarification_cases = [case for case in dataset["cases"] if case["expected"].get("clarification")]
    clarification = sum(
        by_id.get(case["id"], {}).get("classification") == "CLARIFICATION_REQUIRED"
        for case in clarification_cases
    )

    table_recall: list[float] = []
    table_precision: list[float] = []
    relationship_accuracy: list[float] = []
    for case in dataset["cases"]:
        outcome = by_id.get(case["id"])
        if outcome is None:
            continue
        expected_tables = set(case["expected"].get("tables", []))
        actual_tables = set(outcome.get("retrieved_tables", []))
        if expected_tables:
            table_recall.append(len(expected_tables & actual_tables) / len(expected_tables))
            table_precision.append(len(expected_tables & actual_tables) / len(actual_tables or {"_none"}))
        expected_relationships = set(case["expected"].get("relationships", []))
        actual_relationships = set(outcome.get("relationships", []))
        if expected_relationships:
            relationship_accuracy.append(
                len(expected_relationships & actual_relationships) / len(expected_relationships)
            )

    categories = Counter(case["category"] for case in dataset["cases"])
    return {
        "case_count": len(dataset["cases"]),
        "outcome_count": len(outcomes),
        "categories": dict(sorted(categories.items())),
        "sql_validity": fraction(valid, len(sql_cases)),
        "sql_safety": fraction(safe, len(safe_cases)),
        "schema_retrieval_recall": round(sum(table_recall) / len(table_recall), 4) if table_recall else None,
        "schema_precision": round(sum(table_precision) / len(table_precision), 4) if table_precision else None,
        "relationship_accuracy": round(sum(relationship_accuracy) / len(relationship_accuracy), 4)
        if relationship_accuracy
        else None,
        "clarification_accuracy": fraction(clarification, len(clarification_cases)),
        "semantic_correctness": fraction(
            sum(bool(outcome.get("semantic_correct")) for outcome in outcomes), len(outcomes)
        ),
        "result_correctness": fraction(
            sum(bool(outcome.get("result_correct")) for outcome in outcomes), len(outcomes)
        ),
        "answer_faithfulness": fraction(
            sum(bool(outcome.get("answer_faithful")) for outcome in outcomes), len(outcomes)
        ),
        "latency_ms": {
            "mean": round(
                sum(float(outcome.get("latency_ms", 0)) for outcome in outcomes) / len(outcomes), 2
            )
            if outcomes
            else None,
            "maximum": max((float(outcome.get("latency_ms", 0)) for outcome in outcomes), default=None),
        },
        "failure_categories": dict(
            sorted(Counter(outcome.get("failure_category") for outcome in outcomes if outcome.get("failure_category")).items())
        ),
        "unknown_outcomes": sorted(set(by_id) - set(expected)),
        "missing_outcomes": sorted(set(expected) - set(by_id)),
    }
