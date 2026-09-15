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
from app.models.visualization import VisualizationSelection
from app.services.pipeline import BasicSqlPipelineService
from app.workflow.graph import DeterministicQueryWorkflow
from app.workflow.state import QueryState, QuestionAnalysis

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


class _WorkflowAnalysis:
    def analyze(self, question: str, clarification_context: str | None) -> QuestionAnalysis:
        return QuestionAnalysis(
            classification="ANSWERABLE",
            requested_metric="event count",
            entities=("events",),
            filters=(),
            time_range=None,
            grouping=(),
            ordering=None,
            limit=None,
            likely_source_tables=("analytics.events",),
            ambiguous_terms=(),
            clarification_question=None,
            clarification_choices=(),
            answerability_reason="The test question is answerable.",
            warnings=(),
        )


class _WorkflowVisualization:
    def select(self, result: Any) -> VisualizationSelection:
        return VisualizationSelection("table", None, (), None, "integration test")


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


def _workflow(
    fixture: PostgresIntegrationFixture,
    sql: str,
) -> DeterministicQueryWorkflow:
    settings = fixture_settings(fixture)
    source = create_source_database(settings)
    services = DatabaseServices(source=source)
    from app.database.source_introspection import SourceIntrospector

    snapshot = SourceIntrospector(source).introspect()
    return DeterministicQueryWorkflow(
        settings,
        services,
        analysis_service=_WorkflowAnalysis(),
        retrieval_service=_Retrieval(snapshot),
        sql_generation_service=_Generation(sql),
        answer_service=_Answer(),
        visualization_selector=_WorkflowVisualization(),  # type: ignore[arg-type]
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


@pytest.mark.integration
def test_deterministic_workflow_review_mode_stops_before_source_execution(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    source = create_source_database(settings)
    services = DatabaseServices(source=source)
    from app.database.source_introspection import SourceIntrospector

    snapshot = SourceIntrospector(source).introspect()
    workflow = DeterministicQueryWorkflow(
        settings,
        services,
        analysis_service=_WorkflowAnalysis(),
        retrieval_service=_Retrieval(snapshot),
        sql_generation_service=_Generation("SELECT count(*) AS event_count FROM analytics.events"),
        answer_service=_Answer(),
        visualization_selector=_WorkflowVisualization(),  # type: ignore[arg-type]
        snapshot_provider=lambda _: snapshot,
    )

    state = workflow.run("How many events exist?", execution_mode="REVIEW")

    assert state.state == QueryState.READY_FOR_REVIEW
    assert state.result is None
    assert state.validation is not None and state.validation.passed


@pytest.mark.integration
def test_deterministic_workflow_auto_mode_executes_source_only_query(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    source = create_source_database(settings)
    services = DatabaseServices(source=source)
    from app.database.source_introspection import SourceIntrospector

    snapshot = SourceIntrospector(source).introspect()
    workflow = DeterministicQueryWorkflow(
        settings,
        services,
        analysis_service=_WorkflowAnalysis(),
        retrieval_service=_Retrieval(snapshot),
        sql_generation_service=_Generation("SELECT count(*) AS event_count FROM analytics.events"),
        answer_service=_Answer(),
        visualization_selector=_WorkflowVisualization(),  # type: ignore[arg-type]
        snapshot_provider=lambda _: snapshot,
    )

    state = workflow.run("How many events exist?", execution_mode="AUTO")

    assert state.state == QueryState.COMPLETED
    assert state.result is not None
    assert state.result.columns == ("event_count",)
    assert state.result.row_count == 1


@pytest.mark.integration
def test_review_approval_executes_exact_validated_sql(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    workflow = _workflow(
        postgres_fixture,
        "SELECT count(*) AS event_count FROM analytics.events",
    )

    ready = workflow.run("How many events exist?")
    assert ready.proposal is not None
    approved = workflow.approve(ready, sql_version=ready.proposal.sql_hash)
    completed = workflow.execute_approved(approved)

    assert completed.state == QueryState.COMPLETED
    assert completed.result is not None
    assert completed.result.executed_sql_hash == ready.proposal.sql_hash


@pytest.mark.integration
def test_review_edit_requires_new_approval(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    workflow = _workflow(
        postgres_fixture,
        "SELECT count(*) AS event_count FROM analytics.events",
    )

    ready = workflow.run("How many events exist?")
    edited = workflow.edit_sql(
        ready,
        "SELECT count(*) AS total_events FROM analytics.events",
    )

    assert edited.state == QueryState.READY_FOR_REVIEW
    assert edited.approval_sql_hash is None
    assert edited.validation is not None and edited.validation.passed
    assert edited.proposal is not None
    approved = workflow.approve(edited, sql_version=edited.proposal.sql_hash)
    completed = workflow.execute_approved(approved)

    assert completed.result is not None
    assert completed.result.executed_sql_hash == edited.proposal.sql_hash


@pytest.mark.integration
def test_regeneration_preserves_review_gate(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    workflow = _workflow(
        postgres_fixture,
        "SELECT count(*) AS event_count FROM analytics.events",
    )

    ready = workflow.run("How many events exist?")
    regenerated = workflow.regenerate(ready)

    assert regenerated.state == QueryState.READY_FOR_REVIEW
    assert regenerated.question == ready.question
    assert regenerated.query_id == ready.query_id
    assert regenerated.result is None
