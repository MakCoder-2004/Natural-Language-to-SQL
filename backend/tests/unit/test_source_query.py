"""Unit tests for source-only execution and result normalization."""

from datetime import date
from typing import Any, cast

import pytest
from app.config import Settings
from app.database.errors import QueryExecutionError
from app.database.source_connection import SourceDatabase
from app.database.source_execution import SourceExecutionBinding
from app.database.source_query import ReadonlySqlExecutor
from app.models.sql import SqlValidationResult, sql_hash
from sqlalchemy import create_engine, text


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "max_returned_rows": 2,
        "max_result_bytes": 500,
    }
    values.update(overrides)
    settings_constructor: Any = Settings
    return cast(Settings, settings_constructor(**values))


def _binding() -> SourceExecutionBinding:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE values_table (name TEXT, amount NUMERIC)"))
        connection.execute(
            text("INSERT INTO values_table VALUES ('a', 1.2), ('b', 2.3), ('c', 3.4)")
        )
    return SourceExecutionBinding(SourceDatabase(engine=engine, schema_scope=("main",)))


def _validation(sql: str) -> SqlValidationResult:
    return SqlValidationResult(
        passed=True,
        sql=sql,
        sql_hash=sql_hash(sql),
        referenced_schemas=(),
        referenced_relations=(),
        referenced_columns=(),
        blocking_errors=(),
        warnings=(),
        applied_limits=(),
        read_only=True,
        single_statement=True,
    )


def test_executor_normalizes_rows_and_marks_row_truncation() -> None:
    result = ReadonlySqlExecutor(_settings()).execute(
        _binding(), _validation("SELECT name, amount FROM values_table ORDER BY name")
    )

    assert result.columns == ("name", "amount")
    assert result.rows[0][0] == "a"
    assert str(result.rows[0][1]).startswith("1.2")
    assert result.rows[1][0] == "b"
    assert str(result.rows[1][1]).startswith("2.3")
    assert result.truncated
    assert "result_row_limit_reached" in result.warnings


def test_empty_result_is_successful() -> None:
    result = ReadonlySqlExecutor(_settings()).execute(
        _binding(), _validation("SELECT name FROM values_table WHERE name = 'missing'")
    )

    assert result.is_empty
    assert not result.truncated
    assert result.warnings == ()


def test_exact_validation_is_required() -> None:
    validation = _validation("SELECT 1")
    validation = SqlValidationResult(
        passed=True,
        sql="SELECT 2",
        sql_hash=validation.sql_hash,
        referenced_schemas=(),
        referenced_relations=(),
        referenced_columns=(),
        blocking_errors=(),
        warnings=(),
        applied_limits=(),
        read_only=True,
        single_statement=True,
    )

    with pytest.raises(QueryExecutionError):
        ReadonlySqlExecutor(_settings()).execute(_binding(), validation)


def test_dates_are_normalized_to_iso_strings() -> None:
    from app.database.source_query import _normalize_value

    assert _normalize_value(date(2025, 1, 2)) == "2025-01-02"
