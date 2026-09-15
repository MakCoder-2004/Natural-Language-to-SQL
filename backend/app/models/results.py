"""Stable result models returned by source query execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Normalized rows and explicit resource-limit state."""

    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    row_count: int
    returned_row_count: int
    truncated: bool
    result_bytes: int
    warnings: tuple[str, ...]
    executed_sql_hash: str

    @property
    def is_empty(self) -> bool:
        """Return whether the valid query returned zero rows."""

        return self.row_count == 0


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Answer text constrained to executed result data."""

    answer: str
    caveats: tuple[str, ...]
    evidence_summary: str
