from __future__ import annotations

from app.models.query import QueryRequest
from app.workflow.state import QueryState, QueryWorkflowState
from app.workflow.transitions import ALLOWED_TRANSITIONS


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert ALLOWED_TRANSITIONS[QueryState.COMPLETED] == frozenset()
    assert ALLOWED_TRANSITIONS[QueryState.FAILED] == frozenset()


def test_clarification_can_only_resume_analysis() -> None:
    assert ALLOWED_TRANSITIONS[QueryState.CLARIFICATION_REQUIRED] == frozenset(
        {QueryState.ANALYZING}
    )


def test_edited_sql_can_only_return_to_validation() -> None:
    assert ALLOWED_TRANSITIONS[QueryState.EDITED] == frozenset({QueryState.VALIDATING})


def test_workflow_state_starts_received() -> None:
    state = QueryWorkflowState.from_request(QueryRequest.create("question"))
    assert state.state == QueryState.RECEIVED
