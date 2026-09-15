"""Unit tests for conservative SQL validation."""

from typing import Any

import pytest
from app.config import Settings
from app.database.models import (
    DatabaseIdentity,
    RelationMetadata,
    SchemaMetadata,
    SourceColumnMetadata,
    SourceSchemaSnapshot,
)
from app.validation.sql import SqlValidationService


def _snapshot() -> SourceSchemaSnapshot:
    relation = RelationMetadata(
        schema_name="analytics",
        name="events",
        kind="table",
        columns=(
            SourceColumnMetadata("occurred_at", 1, "timestamp", False),
            SourceColumnMetadata("category", 2, "text", True),
            SourceColumnMetadata("amount", 3, "numeric", True),
            SourceColumnMetadata("event_name", 4, "text", True),
        ),
    )
    return SourceSchemaSnapshot(
        identity=DatabaseIdentity("source", "readonly"),
        scope=("analytics",),
        schemas=(SchemaMetadata("analytics", (relation,)),),
        fingerprint="fingerprint",
    )


def test_valid_select_and_aggregation_are_authorized() -> None:
    result = SqlValidationService().validate(
        "SELECT category, sum(amount) AS total FROM analytics.events GROUP BY category",
        _snapshot(),
    )

    assert result.passed
    assert result.read_only
    assert result.single_statement
    assert result.referenced_relations == ("analytics.events",)
    assert "analytics.events.amount" in result.referenced_columns


def test_configured_resource_limits_are_recorded_on_authorization() -> None:
    settings_constructor: Any = Settings
    settings = settings_constructor(_env_file=None)
    result = SqlValidationService(settings).validate("SELECT 1", _snapshot())

    assert result.passed
    assert result.applied_limits == (
        "statement_timeout",
        "max_returned_rows",
        "max_result_bytes",
    )


def test_select_without_source_relation_is_allowed() -> None:
    result = SqlValidationService().validate("SELECT 1", _snapshot())

    assert result.passed
    assert result.referenced_relations == ()


def test_write_and_multiple_statements_are_rejected() -> None:
    validator = SqlValidationService()

    assert not validator.validate("UPDATE analytics.events SET amount = 0", _snapshot()).passed
    assert validator.validate("SELECT 1; SELECT 2", _snapshot()).blocking_errors == (
        "multiple_statements",
    )


def test_unknown_relation_and_column_are_rejected() -> None:
    validator = SqlValidationService()

    unknown_relation = validator.validate("SELECT * FROM analytics.missing", _snapshot())
    unknown_column = validator.validate("SELECT missing FROM analytics.events", _snapshot())

    assert unknown_relation.blocking_errors == ("unknown_relation",)
    assert unknown_column.blocking_errors == ("unknown_column",)


def test_quoted_mixed_case_relation_is_validated_case_safely() -> None:
    relation = RelationMetadata(
        schema_name="public",
        name="Order",
        kind="table",
        columns=(SourceColumnMetadata("created_at", 1, "timestamp", False),),
    )
    snapshot = SourceSchemaSnapshot(
        identity=DatabaseIdentity("source", "readonly"),
        scope=("public",),
        schemas=(SchemaMetadata("public", (relation,)),),
        fingerprint="fingerprint",
    )

    result = SqlValidationService().validate(
        'SELECT COUNT(*) FROM "public"."Order" '
        "WHERE EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)",
        snapshot,
    )

    assert result.passed


def test_read_only_cte_and_aliases_are_supported() -> None:
    result = SqlValidationService().validate(
        "WITH recent AS (SELECT event_name FROM analytics.events) "
        "SELECT recent.event_name FROM recent",
        _snapshot(),
    )

    assert result.passed
    assert result.referenced_relations == ("analytics.events",)


@pytest.mark.parametrize(
    ("sql", "error"),
    [
        ("INSERT INTO analytics.events (event_id) VALUES (1)", "not_read_only"),
        ("DELETE FROM analytics.events", "not_read_only"),
        (
            "MERGE INTO analytics.events USING analytics.events ON false WHEN MATCHED THEN DELETE",
            "not_read_only",
        ),
        ("CREATE TABLE analytics.nope (id integer)", "not_read_only"),
        ("ALTER TABLE analytics.events ADD COLUMN nope text", "not_read_only"),
        ("DROP TABLE analytics.events", "not_read_only"),
        ("TRUNCATE analytics.events", "not_read_only"),
        ("GRANT SELECT ON analytics.events TO public", "not_read_only"),
        ("REVOKE SELECT ON analytics.events FROM public", "not_read_only"),
        ("BEGIN", "not_read_only"),
        ("COMMIT", "not_read_only"),
        ("ROLLBACK", "not_read_only"),
        ("SET statement_timeout = 0", "not_read_only"),
        ("SELECT * INTO analytics.copy_of_events FROM analytics.events", "not_read_only"),
        ("SELECT * FROM analytics.events FOR UPDATE", "not_read_only"),
        ("SELECT pg_sleep(1)", "suspicious_function"),
        ("SELECT nextval('events_event_id_seq')", "suspicious_function"),
    ],
)
def test_statement_policy_rejects_unsafe_categories(sql: str, error: str) -> None:
    result = SqlValidationService().validate(sql, _snapshot())

    assert not result.passed
    assert error in result.blocking_errors


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1 /* comment */ ; /* another comment */ SELECT 2",
        "/* harmless prefix */ SELECT 1; -- hidden second statement\n SELECT 2",
    ],
)
def test_comment_and_formatting_obfuscation_does_not_bypass_statement_policy(sql: str) -> None:
    result = SqlValidationService().validate(sql, _snapshot())

    assert not result.passed
    assert result.blocking_errors == ("multiple_statements",)


def test_out_of_scope_schema_and_database_qualified_references_are_rejected() -> None:
    validator = SqlValidationService()

    out_of_scope = validator.validate("SELECT * FROM internal.events", _snapshot())
    database_qualified = validator.validate("SELECT * FROM index_db.analytics.events", _snapshot())

    assert out_of_scope.blocking_errors == ("disallowed_schema",)
    assert database_qualified.blocking_errors == ("index_database_reference",)


def test_data_modifying_cte_is_rejected() -> None:
    result = SqlValidationService().validate(
        "WITH changed AS (DELETE FROM analytics.events RETURNING event_id) SELECT * FROM changed",
        _snapshot(),
    )

    assert not result.passed
    assert result.blocking_errors == ("not_read_only",)


def test_ambiguous_unqualified_columns_are_rejected() -> None:
    snapshot = _snapshot()
    accounts = RelationMetadata(
        schema_name="analytics",
        name="accounts",
        kind="table",
        columns=(SourceColumnMetadata("event_name", 1, "text", True),),
    )
    snapshot = SourceSchemaSnapshot(
        identity=snapshot.identity,
        scope=snapshot.scope,
        schemas=(SchemaMetadata("analytics", (accounts, snapshot.schemas[0].relations[0])),),
        fingerprint=snapshot.fingerprint,
    )

    result = SqlValidationService().validate(
        "SELECT event_name FROM analytics.accounts JOIN analytics.events ON true",
        snapshot,
    )

    assert result.blocking_errors == ("ambiguous_column",)
