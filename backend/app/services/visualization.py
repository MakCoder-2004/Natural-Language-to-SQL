"""Deterministic visualization selection from normalized query results."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models.results import QueryResult
from app.models.visualization import VisualizationSelection


class VisualizationSelector:
    """Choose a safe presentation shape without asking the model."""

    def select(self, result: QueryResult) -> VisualizationSelection:
        """Select a chart shape from columns and returned values."""

        if result.is_empty:
            return VisualizationSelection("none", None, (), None, "empty_result")
        if len(result.columns) == 1 and all(_is_numeric(row[0]) for row in result.rows if row):
            return VisualizationSelection("kpi", None, (result.columns[0],), None, "single_metric")
        if len(result.columns) >= 2:
            time_column = next(
                (column for column in result.columns if _looks_temporal(column, result)), None
            )
            numeric_columns = tuple(
                column
                for index, column in enumerate(result.columns)
                if any(_is_numeric(row[index]) for row in result.rows if len(row) > index)
            )
            if time_column is not None and numeric_columns:
                return VisualizationSelection(
                    "line", time_column, numeric_columns, None, "temporal_metric"
                )
            if numeric_columns:
                category_column = next(
                    (column for column in result.columns if column not in numeric_columns), None
                )
                if category_column is not None:
                    return VisualizationSelection(
                        "bar",
                        category_column,
                        numeric_columns,
                        category_column,
                        "category_metric",
                    )
        return VisualizationSelection("table", None, (), None, "tabular_result")


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _looks_temporal(column: str, result: QueryResult) -> bool:
    normalized = column.lower()
    if any(token in normalized for token in ("date", "time", "day", "month", "year")):
        return True
    index = result.columns.index(column)
    return any(
        isinstance(row[index], (date, datetime))
        or (isinstance(row[index], str) and "-" in row[index])
        for row in result.rows
        if len(row) > index
    )
