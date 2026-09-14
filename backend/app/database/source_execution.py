"""Source-only execution dependency boundary for later validated SQL work."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Connection

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

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Expose only the explicitly bound source connection to later executors."""

        with self.database.connect() as connection:
            yield connection
