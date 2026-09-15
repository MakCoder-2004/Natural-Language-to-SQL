"""Public request and response contracts for the query API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import DEFAULT_MAX_QUESTION_LENGTH
from app.models.results import GroundedAnswer, QueryResult
from app.models.sql import SqlInspector, SqlValidationResult
from app.models.visualization import VisualizationSelection
from app.workflow.state import QueryState, QueryWorkflowState


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryCreateRequest(ApiModel):
    question: str = Field(min_length=1, max_length=DEFAULT_MAX_QUESTION_LENGTH)
    execution_mode: Literal["REVIEW", "AUTO"] = "REVIEW"

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question cannot be blank")
        return value


class ClarificationRequest(ApiModel):
    clarification: str = Field(min_length=1, max_length=DEFAULT_MAX_QUESTION_LENGTH)

    @field_validator("clarification")
    @classmethod
    def clarification_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("clarification cannot be blank")
        return value


class SqlEditRequest(ApiModel):
    sql: str = Field(min_length=1, max_length=100_000)

    @field_validator("sql")
    @classmethod
    def sql_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("sql cannot be blank")
        return value


class ApprovalRequest(ApiModel):
    sql_version: str = Field(min_length=1, max_length=128)


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(ApiModel):
    error: ErrorBody
    query_id: UUID | None = None
    status: QueryState | None = None


class SqlValidationResponse(ApiModel):
    passed: bool
    sql_hash: str
    referenced_schemas: tuple[str, ...]
    referenced_relations: tuple[str, ...]
    referenced_columns: tuple[str, ...]
    blocking_errors: tuple[str, ...]
    warnings: tuple[str, ...]
    applied_limits: tuple[str, ...]
    read_only: bool
    single_statement: bool

    @classmethod
    def from_domain(cls, value: SqlValidationResult) -> SqlValidationResponse:
        return cls(
            passed=value.passed,
            sql_hash=value.sql_hash,
            referenced_schemas=value.referenced_schemas,
            referenced_relations=value.referenced_relations,
            referenced_columns=value.referenced_columns,
            blocking_errors=value.blocking_errors,
            warnings=value.warnings,
            applied_limits=value.applied_limits,
            read_only=value.read_only,
            single_statement=value.single_statement,
        )


class SqlInspectorResponse(ApiModel):
    sql: str
    original_sql: str | None
    sql_version: str
    interpretation: str
    tables_used: tuple[str, ...]
    assumptions: tuple[str, ...]
    validation_passed: bool
    blocking_errors: tuple[str, ...]
    read_only: bool
    approved_source: bool
    single_statement: bool
    applied_limits: tuple[str, ...]
    warnings: tuple[str, ...]
    approval_required: bool
    approved: bool
    stale_approval: bool

    @classmethod
    def from_domain(cls, value: SqlInspector) -> SqlInspectorResponse:
        return cls(
            sql=value.sql,
            original_sql=value.original_sql,
            sql_version=value.sql_version,
            interpretation=value.interpretation,
            tables_used=value.tables_used,
            assumptions=value.assumptions,
            validation_passed=value.validation_passed,
            blocking_errors=value.blocking_errors,
            read_only=value.read_only,
            approved_source=value.approved_source,
            single_statement=value.single_statement,
            applied_limits=value.applied_limits,
            warnings=value.warnings,
            approval_required=value.approval_required,
            approved=value.approved,
            stale_approval=value.stale_approval,
        )


class QueryResultResponse(ApiModel):
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    row_count: int
    returned_row_count: int
    truncated: bool
    result_bytes: int
    warnings: tuple[str, ...]
    executed_sql_hash: str

    @classmethod
    def from_domain(cls, value: QueryResult) -> QueryResultResponse:
        return cls(
            columns=value.columns,
            rows=value.rows,
            row_count=value.row_count,
            returned_row_count=value.returned_row_count,
            truncated=value.truncated,
            result_bytes=value.result_bytes,
            warnings=value.warnings,
            executed_sql_hash=value.executed_sql_hash,
        )


class GroundedAnswerResponse(ApiModel):
    answer: str
    caveats: tuple[str, ...]
    evidence_summary: str

    @classmethod
    def from_domain(cls, value: GroundedAnswer) -> GroundedAnswerResponse:
        return cls(
            answer=value.answer,
            caveats=value.caveats,
            evidence_summary=value.evidence_summary,
        )


class VisualizationResponse(ApiModel):
    kind: str
    x_column: str | None
    y_columns: tuple[str, ...]
    category_column: str | None
    reason: str

    @classmethod
    def from_domain(cls, value: VisualizationSelection) -> VisualizationResponse:
        return cls(
            kind=value.kind,
            x_column=value.x_column,
            y_columns=value.y_columns,
            category_column=value.category_column,
            reason=value.reason,
        )


class ClarificationResponse(ApiModel):
    question: str | None
    choices: tuple[str, ...]


class QueryResponse(ApiModel):
    query_id: UUID
    pipeline_run_id: UUID
    question: str
    execution_mode: Literal["REVIEW", "AUTO"]
    status: QueryState
    clarification: ClarificationResponse | None = None
    sql_inspector: SqlInspectorResponse | None = None
    validation: SqlValidationResponse | None = None
    result: QueryResultResponse | None = None
    answer: GroundedAnswerResponse | None = None
    visualization: VisualizationResponse | None = None
    warnings: tuple[str, ...] = ()
    error: ErrorBody | None = None
    created_at: datetime


def query_response_from_state(state: QueryWorkflowState) -> QueryResponse:
    analysis = state.analysis
    inspector = state.sql_inspector()
    validation = state.validation
    warnings: tuple[str, ...] = inspector.warnings if inspector is not None else ()
    return QueryResponse(
        query_id=state.query_id,
        pipeline_run_id=state.pipeline_run_id,
        question=state.question,
        execution_mode=state.execution_mode,
        status=state.state,
        clarification=(
            ClarificationResponse(
                question=analysis.clarification_question,
                choices=analysis.clarification_choices,
            )
            if analysis is not None and analysis.classification == "CLARIFICATION_REQUIRED"
            else None
        ),
        sql_inspector=SqlInspectorResponse.from_domain(inspector) if inspector else None,
        validation=SqlValidationResponse.from_domain(validation) if validation else None,
        result=QueryResultResponse.from_domain(state.result) if state.result else None,
        answer=GroundedAnswerResponse.from_domain(state.answer) if state.answer else None,
        visualization=VisualizationResponse.from_domain(state.visualization)
        if state.visualization
        else None,
        warnings=warnings,
        error=ErrorBody(
            code=state.error.code,
            message=state.error.message,
            details={"stage": state.error.stage},
        )
        if state.error
        else None,
        created_at=state.created_at,
    )
