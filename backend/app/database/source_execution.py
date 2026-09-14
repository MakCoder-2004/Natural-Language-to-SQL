"""Source-only execution dependency boundary for later validated SQL work."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.errors import DatabaseSeparationError
from app.database.index_connection import IndexDatabase
from app.database.source_connection import SourceDatabase


@dataclass(frozen=True, slots=True)
class SourceExecutionBinding:
    """Bind future read-only execution to one explicit source service."""

    database: SourceDatabase

    def __post_init__(self) -> None:
        if isinstance(self.database, IndexDatabase):
            raise DatabaseSeparationError(
                "Index database handles cannot be used for source execution."
            )
