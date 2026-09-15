"""Validated read-only execution and stable result normalization."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.config import Settings
from app.database.errors import DatabaseServiceError, QueryExecutionError, QueryTimeoutError
from app.database.source_execution import SourceExecutionBinding
from app.models.results import QueryResult
from app.models.sql import SqlValidationResult, sql_hash


class ReadonlySqlExecutor:
    """Execute only the exact SQL authorized by the deterministic validator."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(
        self,
        binding: SourceExecutionBinding,
        validation: SqlValidationResult,
    ) -> QueryResult:
        """Execute a validated query against the explicitly bound source database."""

        if not validation.passed or not validation.read_only or not validation.single_statement:
            raise QueryExecutionError("Only a passing read-only validation can be executed.")
        if validation.sql_hash != sql_hash(validation.sql):
            raise QueryExecutionError("The validated SQL version is inconsistent.")
        try:
            with binding.connect() as connection:
                cursor = connection.exec_driver_sql(validation.sql)
                columns = tuple(str(key) for key in cursor.keys())
                raw_rows = cursor.fetchmany(self.settings.max_returned_rows + 1)
        except DatabaseServiceError:
            raise
        except DBAPIError as exc:
            if _is_statement_timeout(exc):
                raise QueryTimeoutError(
                    "The source query exceeded the configured execution time limit."
                ) from exc
            raise QueryExecutionError("The source query could not be executed.") from exc
        except SQLAlchemyError as exc:
            raise QueryExecutionError("The source query could not be executed.") from exc
        except Exception as exc:
            raise QueryExecutionError("The source query could not be executed.") from exc

        return _normalize_result(
            columns=columns,
            raw_rows=raw_rows,
            sql_hash=validation.sql_hash,
            max_rows=self.settings.max_returned_rows,
            max_bytes=self.settings.max_result_bytes,
        )


def _normalize_result(
    *,
    columns: tuple[str, ...],
    raw_rows: Sequence[Sequence[Any]],
    sql_hash: str,
    max_rows: int,
    max_bytes: int,
) -> QueryResult:
    """Normalize driver values while enforcing row and serialized-byte limits."""

    truncated = len(raw_rows) > max_rows
    normalized_rows: list[tuple[Any, ...]] = []
    warnings: list[str] = []
    for raw_row in raw_rows[:max_rows]:
        candidate = tuple(_normalize_value(value) for value in raw_row)
        candidate_payload = {"columns": columns, "rows": (*normalized_rows, candidate)}
        candidate_size = _json_size(candidate_payload)
        if candidate_size > max_bytes:
            truncated = True
            warnings.append("result_byte_limit_reached")
            break
        normalized_rows.append(candidate)

    if len(raw_rows) > max_rows:
        warnings.append("result_row_limit_reached")
    result_bytes = _json_size({"columns": columns, "rows": normalized_rows})
    return QueryResult(
        columns=columns,
        rows=tuple(normalized_rows),
        row_count=len(normalized_rows),
        returned_row_count=len(normalized_rows),
        truncated=truncated,
        result_bytes=result_bytes,
        warnings=tuple(warnings),
        executed_sql_hash=sql_hash,
    )


def _normalize_value(value: Any) -> Any:
    """Convert common PostgreSQL values into stable JSON-compatible values."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    return str(value)


def _json_size(value: Any) -> int:
    """Return the UTF-8 size of a compact, stable JSON representation."""

    return len(json.dumps(value, default=str, separators=(",", ":"), ensure_ascii=False).encode())


def _is_statement_timeout(error: DBAPIError) -> bool:
    """Recognize PostgreSQL's server-side statement timeout without exposing details."""

    original = error.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    return sqlstate == "57014"
