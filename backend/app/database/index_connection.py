"""Connection service for the local schema-index PostgreSQL database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Connection, Engine
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.config import Settings
from app.database.engine import create_database_engine, parse_postgres_url
from app.database.errors import DatabaseUnavailableError


@dataclass(frozen=True, slots=True)
class IndexDatabase:
    """Nominal index boundary that cannot be used as a source database."""

    engine: Engine

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Yield an index connection and translate transport failures safely."""

        try:
            with self.engine.connect() as connection:
                yield connection
        except OperationalError as exc:
            raise DatabaseUnavailableError("The index database is unavailable.") from exc
        except DBAPIError as exc:
            raise DatabaseUnavailableError("The index database operation failed.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The index database operation failed.") from exc

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        """Yield a transactional index connection and translate failures safely."""

        try:
            with self.engine.begin() as connection:
                yield connection
        except OperationalError as exc:
            raise DatabaseUnavailableError("The index database is unavailable.") from exc
        except DBAPIError as exc:
            raise DatabaseUnavailableError("The index database operation failed.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The index database operation failed.") from exc

    def dispose(self) -> None:
        """Release pooled index connections."""

        self.engine.dispose()


def create_index_database(settings: Settings) -> IndexDatabase:
    """Create the local index database boundary from backend-owned settings."""

    url = parse_postgres_url(settings.index_database_url, "INDEX_DATABASE_URL")
    engine = create_database_engine(
        url,
        settings,
        pool_size=settings.index_pool_size,
        max_overflow=settings.index_max_overflow,
        pool_timeout=settings.index_pool_timeout_seconds,
        pool_recycle=settings.index_pool_recycle_seconds,
    )
    return IndexDatabase(engine=engine)
