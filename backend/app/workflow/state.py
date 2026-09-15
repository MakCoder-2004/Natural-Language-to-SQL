"""Immutable state contracts for the deterministic query workflow."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from app.models.pipeline import PipelineResult
from app.models.query import QueryRequest
from app.models.results import GroundedAnswer, QueryResult
from app.models.retrieval import RetrievalResult
from app.models.sql import SqlProposal, SqlValidationResult
from app.models.visualization import VisualizationSelection


class QueryState(StrEnum):
    """Explicit lifecycle states from request receipt to completion."""

    RECEIVED = "RECEIVED"
    ANALYZING = "ANALYZING"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    SCHEMA_RETRIEVED = "SCHEMA_RETRIEVED"
    SQL_GENERATED = "SQL_GENERATED"
    VALIDATING = "VALIDATING"
    SQL_CORRECTION = "SQL_CORRECTION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    EDITED = "EDITED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    ANSWER_GENERATED = "ANSWER_GENERATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ExecutionMode = Literal["REVIEW", "AUTO"]
AnalysisClassification = Literal[
    "ANSWERABLE", "CLARIFICATION_REQUIRED", "IMPOSSIBLE", "UNSUPPORTED"
]


@dataclass(frozen=True, slots=True)
class QuestionAnalysis:
    """Validated interpretation of the user's question."""

    classification: AnalysisClassification
    requested_metric: str
    entities: tuple[str, ...]
    filters: tuple[str, ...]
    time_range: str | None
    grouping: tuple[str, ...]
    ordering: str | None
    limit: int | None
    likely_source_tables: tuple[str, ...]
    ambiguous_terms: tuple[str, ...]
    clarification_question: str | None
    clarification_choices: tuple[str, ...]
    answerability_reason: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowErrorInfo:
    """Safe error data retained in failed workflow state."""

    code: str
    message: str
    stage: str


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """One backend-owned lifecycle transition."""

    from_state: QueryState
    to_state: QueryState
    reason: str
    at: datetime


@dataclass(frozen=True, slots=True)
class QueryWorkflowState:
    """Complete immutable state for one query workflow run."""

    query_id: UUID
    pipeline_run_id: UUID
    question: str
    execution_mode: ExecutionMode = "REVIEW"
    state: QueryState = QueryState.RECEIVED
    clarification_context: str | None = None
    analysis: QuestionAnalysis | None = None
    retrieval: RetrievalResult | None = None
    proposal: SqlProposal | None = None
    validation: SqlValidationResult | None = None
    validated_sql_hash: str | None = None
    approval_sql_hash: str | None = None
    result: QueryResult | None = None
    answer: GroundedAnswer | None = None
    visualization: VisualizationSelection | None = None
    correction_attempts: int = 0
    regeneration_count: int = 0
    source_fingerprint: str | None = None
    index_fingerprint: str | None = None
    error: WorkflowErrorInfo | None = None
    stage_timings_ms: dict[str, float] = field(default_factory=dict)
    transitions: tuple[TransitionRecord, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_request(
        cls,
        request: QueryRequest,
        *,
        execution_mode: ExecutionMode = "REVIEW",
        clarification_context: str | None = None,
    ) -> QueryWorkflowState:
        """Create backend-owned initial state from a validated request."""

        return cls(
            query_id=request.query_id,
            pipeline_run_id=request.pipeline_run_id,
            question=request.question,
            execution_mode=execution_mode,
            clarification_context=clarification_context,
        )

    def evolve(self, **changes: Any) -> QueryWorkflowState:
        """Return a new state without mutating this workflow state."""

        return replace(self, **changes)


def pipeline_result_from_state(state: QueryWorkflowState) -> PipelineResult:
    """Build the existing complete pipeline result from a completed state."""

    if (
        state.retrieval is None
        or state.proposal is None
        or state.validation is None
        or state.result is None
        or state.answer is None
        or state.visualization is None
    ):
        raise ValueError("Completed workflow state is missing pipeline result data.")
    return PipelineResult(
        query_id=state.query_id,
        pipeline_run_id=state.pipeline_run_id,
        question=state.question,
        retrieval=state.retrieval,
        proposal=state.proposal,
        validation=state.validation,
        result=state.result,
        answer=state.answer,
        visualization=state.visualization,
    )
