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
from app.database.errors import (
    DatabasePermissionError,
    DatabaseSeparationError,
    DatabaseUnavailableError,
    QueryExecutionError,
    QueryTimeoutError,
)


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
            if _is_statement_timeout(exc):
                raise QueryTimeoutError(
                    "The source query exceeded the configured execution time limit."
                ) from exc
            if _is_permission_error(exc):
                raise DatabasePermissionError(
                    "The source database role is not authorized."
                ) from exc
            raise DatabaseUnavailableError("The source database is unavailable.") from exc
        except DBAPIError as exc:
            if _is_statement_timeout(exc):
                raise QueryTimeoutError(
                    "The source query exceeded the configured execution time limit."
                ) from exc
            if _is_permission_error(exc):
                raise DatabasePermissionError(
                    "The source database role is not authorized."
                ) from exc
            if _is_query_error(exc):
                raise QueryExecutionError("The source query could not be executed.") from exc
            raise DatabaseUnavailableError("The source database operation failed.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The source database operation failed.") from exc

    def langchain_database(self, schema_name: str) -> SQLDatabase:
        """Return a scoped LangChain adapter backed by this exact source engine."""

        if schema_name not in self.schema_scope:
            raise DatabaseSeparationError(
                "LangChain SQL access must use an approved source schema."
            )

        try:
            return SQLDatabase(
                engine=self.engine,
                schema=schema_name,
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


def _is_permission_error(error: DBAPIError) -> bool:
    """Recognize PostgreSQL authentication and privilege SQLSTATE classes."""

    sqlstate = getattr(error.orig, "sqlstate", None)
    if isinstance(sqlstate, str) and (sqlstate == "42501" or sqlstate.startswith("28")):
        return True
    pgcode = getattr(error.orig, "pgcode", None)
    if isinstance(pgcode, str) and (pgcode == "42501" or pgcode.startswith("28")):
        return True
    message = str(error.orig).lower()
    return "authentication failed" in message or "no pg_hba.conf" in message


def _is_statement_timeout(error: DBAPIError) -> bool:
    """Recognize PostgreSQL's statement timeout SQLSTATE."""

    original = error.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    return sqlstate == "57014"


def _is_query_error(error: DBAPIError) -> bool:
    """Recognize SQL/data errors that do not indicate a broken database."""

    sqlstate = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
    return isinstance(sqlstate, str) and sqlstate[:2] in {"22", "42"}


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
