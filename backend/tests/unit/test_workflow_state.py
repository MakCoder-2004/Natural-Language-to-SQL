from __future__ import annotations

from uuid import uuid4

import pytest
from app.models.query import QueryRequest
from app.workflow.errors import InvalidTransitionError, WorkflowInvariantError
from app.workflow.state import (
    QueryState,
    QueryWorkflowState,
    WorkflowErrorInfo,
)
from app.workflow.transitions import transition


def _state() -> QueryWorkflowState:
    return QueryWorkflowState.from_request(QueryRequest.create("show a metric"))


def test_state_is_immutable_and_preserves_identifiers() -> None:
    state = _state()
    next_state = transition(state, QueryState.ANALYZING, reason="begin analysis")

    assert state.state == QueryState.RECEIVED
    assert next_state.state == QueryState.ANALYZING
    assert next_state.query_id == state.query_id
    assert next_state.pipeline_run_id == state.pipeline_run_id


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(_state(), QueryState.SQL_GENERATED, reason="bypass")


def test_failed_state_requires_safe_error() -> None:
    state = transition(_state(), QueryState.ANALYZING, reason="begin analysis")
    with pytest.raises(WorkflowInvariantError):
        transition(state, QueryState.FAILED, reason="failure without category")

    failed = transition(
        state.evolve(
            error=WorkflowErrorInfo(
                code="unsupported_question",
                message="This question is not supported.",
                stage="analysis",
            )
        ),
        QueryState.FAILED,
        reason="unsupported question",
    )
    assert failed.state == QueryState.FAILED


def test_clarification_state_cannot_contain_sql() -> None:
    state = transition(_state(), QueryState.ANALYZING, reason="begin analysis")
    with pytest.raises(WorkflowInvariantError):
        transition(
            state.evolve(proposal=object()),
            QueryState.CLARIFICATION_REQUIRED,
            reason="ambiguous question",
        )


def test_default_execution_mode_is_review() -> None:
    state = _state()
    assert state.execution_mode == "REVIEW"


def test_request_ids_are_opaque_backend_values() -> None:
    request = QueryRequest(question="show a metric", query_id=uuid4(), pipeline_run_id=uuid4())
    state = QueryWorkflowState.from_request(request)
    assert state.query_id == request.query_id
    assert state.pipeline_run_id == request.pipeline_run_id


def test_sql_inspector_exposes_current_and_original_sql() -> None:
    from app.models.sql import SqlProposal, SqlValidationResult, sql_hash

    original = SqlProposal.create(sql="SELECT 1", interpretation="One")
    current = SqlProposal.create(sql="SELECT 2", interpretation="Two")
    validation = SqlValidationResult(
        True,
        current.sql,
        sql_hash(current.sql),
        ("public",),
        ("public.values",),
        (),
        (),
        ("warning",),
        ("statement_timeout",),
        True,
        True,
    )
    state = _state().evolve(
        proposal=current,
        original_proposal=original,
        validation=validation,
        validated_sql_hash=validation.sql_hash,
    )

    inspector = state.sql_inspector()

    assert inspector is not None
    assert inspector.sql == "SELECT 2"
    assert inspector.original_sql == "SELECT 1"
    assert inspector.sql_version == validation.sql_hash
    assert inspector.validation_passed is True
    assert inspector.approved_source is True
    assert inspector.approval_required is True
    assert inspector.approved is False
    assert inspector.stale_approval is False


def test_sql_inspector_reports_stale_approval() -> None:
    from app.models.sql import SqlProposal, SqlValidationResult, sql_hash

    proposal = SqlProposal.create(sql="SELECT 1", interpretation="One")
    validation = SqlValidationResult(
        True,
        proposal.sql,
        sql_hash(proposal.sql),
        (),
        (),
        (),
        (),
        (),
        (),
        True,
        True,
    )
    state = _state().evolve(
        proposal=proposal,
        validation=validation,
        validated_sql_hash=validation.sql_hash,
        approval_sql_hash=sql_hash("SELECT 2"),
    )

    inspector = state.sql_inspector()

    assert inspector is not None
    assert inspector.approved is False
    assert inspector.stale_approval is True
