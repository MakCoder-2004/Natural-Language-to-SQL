"""Private SQLAlchemy engine construction shared by database boundaries."""

from __future__ import annotations

from typing import Literal

from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.config import Settings
from app.database.errors import DatabaseServiceError

DatabaseField = Literal["SOURCE_DATABASE_URL", "INDEX_DATABASE_URL"]


def parse_postgres_url(value: SecretStr | None, field: DatabaseField) -> URL:
    """Parse a configured PostgreSQL URL without returning its secret contents."""

    if value is None or not value.get_secret_value().strip():
        raise DatabaseServiceError(f"{field} is not configured.")

    try:
        parsed_url = make_url(value.get_secret_value())
    except (ArgumentError, TypeError, ValueError) as exc:
        raise DatabaseServiceError(f"{field} is invalid.") from exc

    if not parsed_url.drivername.startswith("postgresql"):
        raise DatabaseServiceError(f"{field} must be a PostgreSQL URL.")
    return parsed_url


def create_database_engine(
    url: URL,
    settings: Settings,
    *,
    pool_size: int,
    max_overflow: int,
    pool_timeout: int,
    pool_recycle: int,
) -> Engine:
    """Create a bounded PostgreSQL engine with server-side statement timeout."""

    statement_timeout_ms = settings.query_timeout_seconds * 1000
    return create_engine(
        url,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "options": f"-c statement_timeout={statement_timeout_ms}",
        },
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_reset_on_return="rollback",
    )
