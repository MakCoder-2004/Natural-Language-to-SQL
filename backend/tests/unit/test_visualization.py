"""Unit tests for deterministic result-shape selection."""

from app.models.results import QueryResult
from app.services.visualization import VisualizationSelector


def _result(columns: tuple[str, ...], rows: tuple[tuple[object, ...], ...]) -> QueryResult:
    return QueryResult(columns, rows, len(rows), len(rows), False, 1, (), "hash")


def test_selector_chooses_kpi_for_one_numeric_value() -> None:
    selection = VisualizationSelector().select(_result(("total",), ((12,),)))

    assert selection.kind == "kpi"


def test_selector_chooses_line_for_temporal_metric() -> None:
    selection = VisualizationSelector().select(
        _result(("occurred_at", "total"), (("2025-01-01", 2), ("2025-01-02", 3)))
    )

    assert selection.kind == "line"
    assert selection.x_column == "occurred_at"


def test_selector_chooses_table_for_empty_result() -> None:
    selection = VisualizationSelector().select(_result(("name",), ()))

    assert selection.kind == "none"
    assert selection.reason == "empty_result"
