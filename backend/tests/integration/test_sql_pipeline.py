"""Disposable PostgreSQL coverage for the basic SQL pipeline."""

from __future__ import annotations

from typing import Any

import pytest
from app.database.models import SourceSchemaSnapshot
from app.database.services import DatabaseServices
from app.database.source_connection import create_source_database
from app.models.results import GroundedAnswer
from app.models.retrieval import RetrievalDiagnostics, RetrievalLimits, RetrievalResult
from app.models.sql import SqlProposal
from app.services.pipeline import BasicSqlPipelineService

from tests.fixtures.postgres import PostgresIntegrationFixture, fixture_settings


def _retrieval(snapshot: SourceSchemaSnapshot) -> RetrievalResult:
    limits = RetrievalLimits(1, 1, 1, 1, 1, 1, 1, 1, 1_000, 0.2, 0.6, 0.4, 60)
    diagnostics = RetrievalDiagnostics(0, 0, 0, 0, 0, 0, 0, {}, limits)
    return RetrievalResult(
        (), (), (), (), "bounded schema context", snapshot.fingerprint, diagnostics
    )


class _Retrieval:
    def __init__(self, snapshot: SourceSchemaSnapshot) -> None:
        self.snapshot = snapshot

    def retrieve(self, question: str) -> RetrievalResult:
        return _retrieval(self.snapshot)


class _Generation:
    def __init__(self, sql: str) -> None:
        self.sql = sql

    def generate(self, question: str, retrieval: RetrievalResult) -> SqlProposal:
        return SqlProposal.create(
            sql=self.sql,
            interpretation="Returns the requested event data.",
            tables_used=("analytics.events",),
        )


class _Answer:
    def generate(self, question: str, sql: str, result: Any) -> GroundedAnswer:
        if result.is_empty:
            return GroundedAnswer(
                "No matching events were returned.", (), "The query returned zero rows."
            )
        return GroundedAnswer(
            f"The query returned {result.row_count} row(s).",
            (),
            "The answer is based on the executed source query.",
        )


def _pipeline(
    fixture: PostgresIntegrationFixture,
    sql: str,
) -> BasicSqlPipelineService:
    settings = fixture_settings(fixture)
    source = create_source_database(settings)
    services = DatabaseServices(source=source)
    from app.database.source_introspection import SourceIntrospector

    snapshot = SourceIntrospector(source).introspect()
    return BasicSqlPipelineService(
        settings,
        services,
        retrieval_service=_Retrieval(snapshot),
        sql_generation_service=_Generation(sql),
        answer_service=_Answer(),
        snapshot_provider=lambda _: snapshot,
    )


@pytest.mark.integration
def test_clear_question_produces_validated_normalized_result(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    pipeline = _pipeline(
        postgres_fixture,
        "SELECT count(*) AS event_count FROM analytics.events",
    )

    result = pipeline.run("How many events exist?")

    assert result.validation.passed
    assert result.validation.referenced_relations == ("analytics.events",)
    assert result.result.columns == ("event_count",)
    assert result.result.row_count == 1
    assert result.result.truncated is False
    assert result.answer.answer.startswith("The query returned")


@pytest.mark.integration
def test_valid_query_returning_zero_rows_is_not_a_failure(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    pipeline = _pipeline(
        postgres_fixture,
        "SELECT event_name FROM analytics.events WHERE event_name = 'missing'",
    )

    result = pipeline.run("Show missing events")

    assert result.validation.passed
    assert result.result.row_count == 0
    assert result.result.is_empty
    assert result.result.truncated is False
    assert result.answer.answer == "No matching events were returned."
