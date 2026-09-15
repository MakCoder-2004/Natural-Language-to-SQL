from __future__ import annotations

from typing import Any

import pytest
from app.config import Settings
from app.database.errors import ModelServiceError
from app.database.models import (
    DatabaseIdentity,
    RelationMetadata,
    SchemaMetadata,
    SourceSchemaSnapshot,
)
from app.database.services import DatabaseServices
from app.database.source_connection import SourceDatabase
from app.models.results import GroundedAnswer, QueryResult
from app.models.retrieval import RetrievalDiagnostics, RetrievalLimits, RetrievalResult
from app.models.sql import SqlProposal, SqlValidationResult, sql_hash
from app.models.visualization import VisualizationSelection
from app.workflow.errors import WorkflowError
from app.workflow.graph import DeterministicQueryWorkflow
from app.workflow.state import QueryState, QuestionAnalysis
from sqlalchemy import create_engine


def _settings(**overrides: Any) -> Settings:
    return Settings(max_question_length=100, _env_file=None, **overrides)  # type: ignore[call-arg]


def _retrieval() -> RetrievalResult:
    limits = RetrievalLimits(1, 1, 1, 1, 1, 1, 1, 1, 100, 0.2, 0.6, 0.4, 60)
    diagnostics = RetrievalDiagnostics(0, 0, 0, 0, 0, 0, 0, {}, limits)
    return RetrievalResult((), (), (), (), "context", "fingerprint", diagnostics)


def _snapshot() -> SourceSchemaSnapshot:
    return SourceSchemaSnapshot(
        DatabaseIdentity("source", "readonly"),
        ("main",),
        (SchemaMetadata("main", (RelationMetadata("main", "values_table", "table", ()),)),),
        "fingerprint",
    )


class _Analysis:
    def __init__(self, classification: str = "ANSWERABLE") -> None:
        self.classification = classification

    def analyze(self, question: str, clarification_context: str | None) -> QuestionAnalysis:
        return QuestionAnalysis(
            classification=self.classification,  # type: ignore[arg-type]
            requested_metric="count",
            entities=(),
            filters=(),
            time_range=None,
            grouping=(),
            ordering=None,
            limit=None,
            likely_source_tables=(),
            ambiguous_terms=("best",) if self.classification == "CLARIFICATION_REQUIRED" else (),
            clarification_question="What does best mean?"
            if self.classification == "CLARIFICATION_REQUIRED"
            else None,
            clarification_choices=("Highest total spending", "Most orders")
            if self.classification == "CLARIFICATION_REQUIRED"
            else (),
            answerability_reason="Test classification",
            warnings=(),
        )


class _Retrieval:
    def retrieve(self, question: str) -> RetrievalResult:
        return _retrieval()


class _Generation:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, question: str, retrieval: RetrievalResult) -> SqlProposal:
        self.calls += 1
        return SqlProposal.create(sql="SELECT 1", interpretation="Returns one.")


class _Correction:
    def correct(
        self,
        question: str,
        retrieval: RetrievalResult,
        sql: str,
        validation_errors: tuple[str, ...],
    ) -> SqlProposal:
        return SqlProposal.create(sql="SELECT 1", interpretation="Corrected proposal.")


class _FailingCorrection:
    def correct(
        self,
        question: str,
        retrieval: RetrievalResult,
        sql: str,
        validation_errors: tuple[str, ...],
    ) -> SqlProposal:
        raise ModelServiceError("correction model failed")


class _Validation:
    def validate(self, sql: str, snapshot: SourceSchemaSnapshot) -> SqlValidationResult:
        return SqlValidationResult(True, sql, sql_hash(sql), (), (), (), (), (), (), True, True)


class _CorrectingValidation:
    def __init__(self) -> None:
        self.calls = 0

    def validate(self, sql: str, snapshot: SourceSchemaSnapshot) -> SqlValidationResult:
        self.calls += 1
        if self.calls == 1:
            return SqlValidationResult.rejected(sql, errors=("invalid identifier",))
        return SqlValidationResult(True, sql, sql_hash(sql), (), (), (), (), (), (), True, True)


class _AlwaysInvalidValidation:
    def __init__(self) -> None:
        self.calls = 0

    def validate(self, sql: str, snapshot: SourceSchemaSnapshot) -> SqlValidationResult:
        self.calls += 1
        return SqlValidationResult.rejected(sql, errors=("unknown_column",))


class _InvalidEditedValidation:
    def __init__(self) -> None:
        self.calls = 0

    def validate(self, sql: str, snapshot: SourceSchemaSnapshot) -> SqlValidationResult:
        self.calls += 1
        if self.calls == 1:
            return SqlValidationResult(True, sql, sql_hash(sql), (), (), (), (), (), (), True, True)
        return SqlValidationResult.rejected(sql, errors=("unsafe_statement",))


class _Executor:
    def execute(self, binding: Any, validation: SqlValidationResult) -> QueryResult:
        return QueryResult(("value",), ((1,),), 1, 1, False, 1, (), validation.sql_hash)


class _Answer:
    def generate(self, question: str, sql: str, result: QueryResult) -> GroundedAnswer:
        return GroundedAnswer("One.", (), "The query returned one row.")


class _Visualization:
    def select(self, result: QueryResult) -> VisualizationSelection:
        return VisualizationSelection("kpi", None, (), None, "single metric")


def _workflow(
    analysis: Any | None = None,
    validation_service: Any | None = None,
    **settings: Any,
) -> DeterministicQueryWorkflow:
    services = DatabaseServices(SourceDatabase(create_engine("sqlite://"), ("main",)), None)
    return DeterministicQueryWorkflow(
        _settings(**settings),
        services,
        analysis_service=analysis or _Analysis(),
        retrieval_service=_Retrieval(),
        sql_generation_service=_Generation(),
        sql_correction_service=_Correction(),
        validation_service=validation_service or _Validation(),
        executor=_Executor(),
        answer_service=_Answer(),
        visualization_selector=_Visualization(),  # type: ignore[arg-type]
        snapshot_provider=lambda _: _snapshot(),
    )


def test_review_mode_stops_before_execution_and_can_be_approved() -> None:
    workflow = _workflow()

    ready = workflow.run("count values")

    assert ready.state == QueryState.READY_FOR_REVIEW
    assert ready.result is None
    approved = workflow.approve(
        ready, sql_version=ready.proposal.sql_hash if ready.proposal else None
    )
    completed = workflow.execute_approved(approved)
    assert completed.state == QueryState.COMPLETED
    assert completed.result is not None


def test_approval_rejects_stale_sql_version() -> None:
    workflow = _workflow()
    ready = workflow.run("count values")

    with pytest.raises(WorkflowError, match="stale"):
        workflow.approve(ready, sql_version="stale-version")


def test_approval_rejects_auto_mode() -> None:
    workflow = _workflow()
    state = workflow.run("count values", execution_mode="AUTO")

    with pytest.raises(WorkflowError, match="review-ready"):
        workflow.approve(state)


def test_initial_proposal_is_preserved_when_sql_is_edited() -> None:
    workflow = _workflow()

    ready = workflow.run("count values")
    edited = workflow.edit_sql(ready, "SELECT 2")

    assert ready.proposal is not None
    assert edited.original_proposal is not None
    assert edited.original_proposal.sql == ready.proposal.sql
    assert edited.proposal is not None
    assert edited.proposal.sql == "SELECT 2"
    assert edited.approval_sql_hash is None


def test_auto_mode_completes_only_after_validation() -> None:
    completed = _workflow().run("count values", execution_mode="AUTO")

    assert completed.state == QueryState.COMPLETED
    assert completed.validation is not None and completed.validation.passed


def test_ambiguous_question_stops_before_retrieval_and_sql() -> None:
    state = _workflow(_Analysis("CLARIFICATION_REQUIRED")).run("which customers are best?")

    assert state.state == QueryState.CLARIFICATION_REQUIRED
    assert state.proposal is None
    assert state.retrieval is None
    assert state.analysis is not None
    assert state.analysis.clarification_choices


def test_clarification_resumes_the_answerable_workflow() -> None:
    workflow = _workflow(_Analysis("CLARIFICATION_REQUIRED"))
    pending = workflow.run("which customers are best?")

    completed = workflow.resume_clarification(pending, "Highest total spending")

    assert completed.state == QueryState.READY_FOR_REVIEW
    assert completed.clarification_context == "Highest total spending"


def test_impossible_question_fails_without_sql() -> None:
    state = _workflow(_Analysis("IMPOSSIBLE")).run("drop all tables")

    assert state.state == QueryState.FAILED
    assert state.proposal is None
    assert state.error is not None
    assert state.error.code == "impossible"


def test_workflow_result_requires_completion() -> None:
    workflow = _workflow()
    ready = workflow.run("count values")

    with pytest.raises(WorkflowError):
        workflow.result(ready)


def test_validation_correction_is_bounded_and_returns_to_review() -> None:
    validation = _CorrectingValidation()
    services = DatabaseServices(SourceDatabase(create_engine("sqlite://"), ("main",)), None)
    workflow = DeterministicQueryWorkflow(
        _settings(max_correction_retries=1),
        services,
        analysis_service=_Analysis(),
        retrieval_service=_Retrieval(),
        sql_generation_service=_Generation(),
        sql_correction_service=_Correction(),
        validation_service=validation,
        executor=_Executor(),
        answer_service=_Answer(),
        visualization_selector=_Visualization(),  # type: ignore[arg-type]
        snapshot_provider=lambda _: _snapshot(),
    )

    state = workflow.run("count values")

    assert state.state == QueryState.READY_FOR_REVIEW
    assert state.correction_attempts == 1
    assert validation.calls == 2


def test_validation_correction_exhaustion_never_attempts_a_third_retry() -> None:
    validation = _AlwaysInvalidValidation()
    workflow = DeterministicQueryWorkflow(
        _settings(),
        DatabaseServices(SourceDatabase(create_engine("sqlite://"), ("main",)), None),
        analysis_service=_Analysis(),
        retrieval_service=_Retrieval(),
        sql_generation_service=_Generation(),
        sql_correction_service=_Correction(),
        validation_service=validation,
        executor=_Executor(),
        answer_service=_Answer(),
        visualization_selector=_Visualization(),  # type: ignore[arg-type]
        snapshot_provider=lambda _: _snapshot(),
    )

    state = workflow.run("count values")

    assert state.state == QueryState.FAILED
    assert state.error is not None and state.error.code == "correction_exhausted"
    assert state.correction_attempts == 2
    assert validation.calls == 3


def test_correction_failure_stays_failed_without_invalid_transition() -> None:
    workflow = DeterministicQueryWorkflow(
        _settings(max_correction_retries=1),
        DatabaseServices(SourceDatabase(create_engine("sqlite://"), ("main",)), None),
        analysis_service=_Analysis(),
        retrieval_service=_Retrieval(),
        sql_generation_service=_Generation(),
        sql_correction_service=_FailingCorrection(),
        validation_service=_AlwaysInvalidValidation(),
        executor=_Executor(),
        answer_service=_Answer(),
        visualization_selector=_Visualization(),  # type: ignore[arg-type]
        snapshot_provider=lambda _: _snapshot(),
    )

    state = workflow.run("count values")

    assert state.state == QueryState.FAILED
    assert state.error is not None and state.error.code == "model_error"


def test_edited_sql_returns_to_validation_and_review() -> None:
    workflow = _workflow()
    ready = workflow.run("count values")

    edited = workflow.edit_sql(ready, "SELECT 2")

    assert edited.state == QueryState.READY_FOR_REVIEW
    assert edited.proposal is not None and edited.proposal.sql == "SELECT 2"
    assert edited.validation is not None and edited.validation.sql == "SELECT 2"


def test_edited_sql_requires_new_approval_before_execution() -> None:
    workflow = _workflow()
    ready = workflow.run("count values")

    edited = workflow.edit_sql(ready, "SELECT 2")

    assert edited.state == QueryState.READY_FOR_REVIEW
    assert edited.approval_sql_hash is None
    with pytest.raises(WorkflowError, match="approved"):
        workflow.execute_approved(edited)


def test_unsafe_edited_sql_never_reaches_execution() -> None:
    workflow = _workflow(validation_service=_InvalidEditedValidation())
    ready = workflow.run("count values")
    edited = workflow.edit_sql(ready, "DROP TABLE values_table")

    assert edited.state == QueryState.FAILED
    assert edited.error is not None


def test_edited_sql_cannot_retain_an_existing_approval() -> None:
    workflow = _workflow()
    ready = workflow.run("count values")
    approved = workflow.approve(ready)

    edited = workflow.edit_sql(approved.evolve(state=QueryState.READY_FOR_REVIEW), "SELECT 2")

    assert edited.approval_sql_hash is None


def test_regeneration_preserves_context_and_stops_for_review() -> None:
    workflow = _workflow()
    ready = workflow.run("count values", clarification_context="Only completed values")

    regenerated = workflow.regenerate(ready)

    assert regenerated.state == QueryState.READY_FOR_REVIEW
    assert regenerated.query_id == ready.query_id
    assert regenerated.question == ready.question
    assert regenerated.clarification_context == ready.clarification_context
    assert regenerated.execution_mode == "REVIEW"
    assert regenerated.regeneration_count == 1
    assert regenerated.result is None
    assert regenerated.approval_sql_hash is None
    assert regenerated.original_proposal == ready.original_proposal
    assert any(record.to_state == QueryState.REGENERATING for record in regenerated.transitions)


def test_regeneration_is_bounded() -> None:
    workflow = _workflow(max_regeneration_count=1)
    ready = workflow.run("count values")

    regenerated = workflow.regenerate(ready)
    with pytest.raises(WorkflowError, match="maximum number"):
        workflow.regenerate(regenerated)
