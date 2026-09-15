"""Result-shape visualization selection models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VisualizationKind = Literal["table", "kpi", "line", "bar", "composition", "none"]


@dataclass(frozen=True, slots=True)
class VisualizationSelection:
    """A safe, deterministic suggestion for presenting normalized rows."""

    kind: VisualizationKind
    x_column: str | None
    y_columns: tuple[str, ...]
    category_column: str | None
    reason: str
