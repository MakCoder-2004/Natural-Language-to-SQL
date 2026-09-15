"""Unit tests for conservative SQL validation."""

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


def test_read_only_cte_and_aliases_are_supported() -> None:
    result = SqlValidationService().validate(
        "WITH recent AS (SELECT event_name FROM analytics.events) "
        "SELECT recent.event_name FROM recent",
        _snapshot(),
    )

    assert result.passed
    assert result.referenced_relations == ("analytics.events",)
