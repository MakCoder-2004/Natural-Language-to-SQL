"""Connection service for the external source PostgreSQL database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from langchain_community.utilities import SQLDatabase
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.config import Settings
from app.database.engine import create_database_engine, parse_postgres_url
from app.database.errors import DatabaseUnavailableError


@dataclass(frozen=True, slots=True)
class SourceDatabase:
    """Nominal source boundary shared by introspection and future execution."""

    engine: Engine
    schema_scope: tuple[str, ...]

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Yield a source connection and translate transport failures safely."""

        try:
            with self.engine.connect() as connection:
                yield connection
        except OperationalError as exc:
            raise DatabaseUnavailableError("The source database is unavailable.") from exc
        except DBAPIError as exc:
            raise DatabaseUnavailableError("The source database operation failed.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The source database operation failed.") from exc

    def langchain_database(self) -> SQLDatabase:
        """Return LangChain's SQL adapter backed by this exact source engine."""

        try:
            return SQLDatabase(
                engine=self.engine,
                sample_rows_in_table_info=0,
                indexes_in_table_info=False,
                view_support=True,
                lazy_table_reflection=True,
            )
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The source database adapter is unavailable.") from exc

    def dispose(self) -> None:
        """Release pooled source connections."""

        self.engine.dispose()


def create_source_database(settings: Settings) -> SourceDatabase:
    """Create the source database boundary from backend-owned settings."""

    url = parse_postgres_url(settings.source_database_url, "SOURCE_DATABASE_URL")
    engine = create_database_engine(
        url,
        settings,
        pool_size=settings.source_pool_size,
        max_overflow=settings.source_max_overflow,
        pool_timeout=settings.source_pool_timeout_seconds,
        pool_recycle=settings.source_pool_recycle_seconds,
    )
    return SourceDatabase(engine=engine, schema_scope=settings.source_schema_names)
