"""Backend-owned query state transitions and invariants."""

from __future__ import annotations

from datetime import UTC, datetime

from app.workflow.errors import InvalidTransitionError, WorkflowInvariantError
from app.workflow.state import QueryState, QueryWorkflowState, TransitionRecord

ALLOWED_TRANSITIONS: dict[QueryState, frozenset[QueryState]] = {
    QueryState.RECEIVED: frozenset({QueryState.ANALYZING}),
    QueryState.ANALYZING: frozenset(
        {QueryState.CLARIFICATION_REQUIRED, QueryState.SCHEMA_RETRIEVED, QueryState.FAILED}
    ),
    QueryState.CLARIFICATION_REQUIRED: frozenset({QueryState.ANALYZING}),
    QueryState.SCHEMA_RETRIEVED: frozenset({QueryState.SQL_GENERATED, QueryState.FAILED}),
    QueryState.SQL_GENERATED: frozenset({QueryState.VALIDATING, QueryState.FAILED}),
    QueryState.VALIDATING: frozenset(
        {
            QueryState.SQL_CORRECTION,
            QueryState.READY_FOR_REVIEW,
            QueryState.EXECUTING,
            QueryState.FAILED,
        }
    ),
    QueryState.SQL_CORRECTION: frozenset({QueryState.SQL_GENERATED, QueryState.FAILED}),
    QueryState.REGENERATING: frozenset({QueryState.SQL_GENERATED, QueryState.FAILED}),
    QueryState.READY_FOR_REVIEW: frozenset(
        {QueryState.EDITED, QueryState.REGENERATING, QueryState.APPROVED, QueryState.EXECUTING}
    ),
    QueryState.EDITED: frozenset({QueryState.VALIDATING}),
    QueryState.APPROVED: frozenset({QueryState.EXECUTING}),
    QueryState.EXECUTING: frozenset({QueryState.EXECUTED, QueryState.FAILED}),
    QueryState.EXECUTED: frozenset({QueryState.ANSWER_GENERATED}),
    QueryState.ANSWER_GENERATED: frozenset({QueryState.COMPLETED, QueryState.FAILED}),
    QueryState.COMPLETED: frozenset(),
    QueryState.FAILED: frozenset(),
}


def transition(
    state: QueryWorkflowState,
    target: QueryState,
    *,
    reason: str,
) -> QueryWorkflowState:
    """Apply one valid lifecycle transition and verify target invariants."""

    if target not in ALLOWED_TRANSITIONS[state.state]:
        raise InvalidTransitionError(f"Transition from {state.state} to {target} is not allowed.")
    next_state = state.evolve(
        state=target,
        transitions=state.transitions
        + (
            TransitionRecord(
                from_state=state.state,
                to_state=target,
                reason=reason,
                at=datetime.now(UTC),
            ),
        ),
    )
    _validate_invariants(next_state)
    return next_state


def _validate_invariants(state: QueryWorkflowState) -> None:
    """Enforce security-relevant state requirements after transitions."""

    if state.state == QueryState.CLARIFICATION_REQUIRED:
        if state.proposal is not None or state.validation is not None:
            raise WorkflowInvariantError("Clarification state cannot contain executable SQL data.")
    if state.state == QueryState.READY_FOR_REVIEW:
        if state.validation is None or not state.validation.passed:
            raise WorkflowInvariantError("Review state requires passing SQL validation.")
        if state.validated_sql_hash != state.validation.sql_hash:
            raise WorkflowInvariantError("Review state requires the current validated SQL hash.")
        if state.proposal is None or state.proposal.sql_hash != state.validated_sql_hash:
            raise WorkflowInvariantError("Review state requires validation for the current SQL.")
        if (
            state.approval_sql_hash is not None
            and state.approval_sql_hash != state.validated_sql_hash
        ):
            raise WorkflowInvariantError("Review state cannot retain stale approval.")
    if state.state == QueryState.APPROVED:
        if state.execution_mode != "REVIEW":
            raise WorkflowInvariantError("Only Review Mode queries can be approved.")
        if state.approval_sql_hash is None or state.approval_sql_hash != state.validated_sql_hash:
            raise WorkflowInvariantError("Approval must bind to the exact validated SQL hash.")
    if state.state == QueryState.EXECUTING:
        if state.validation is None or not state.validation.passed:
            raise WorkflowInvariantError("Execution requires passing SQL validation.")
        if state.validated_sql_hash != state.validation.sql_hash:
            raise WorkflowInvariantError("Execution requires the current validated SQL hash.")
        if state.execution_mode == "REVIEW" and state.approval_sql_hash != state.validated_sql_hash:
            raise WorkflowInvariantError("Review Mode execution requires exact SQL approval.")
    if state.state == QueryState.COMPLETED:
        if state.result is None or state.result.executed_sql_hash != state.validated_sql_hash:
            raise WorkflowInvariantError("Completion requires the executed validated SQL.")
    if state.state == QueryState.FAILED and state.error is None:
        raise WorkflowInvariantError("Failed state requires safe error information.")
