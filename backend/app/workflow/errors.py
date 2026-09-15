"""Safe workflow errors and machine-readable failure categories."""

from __future__ import annotations


class WorkflowError(RuntimeError):
    """Base error raised when a workflow cannot safely continue."""

    error_code = "workflow_error"


class InvalidTransitionError(WorkflowError):
    """Raised when a query attempts an undefined state transition."""

    error_code = "invalid_workflow_transition"


class WorkflowInvariantError(WorkflowError):
    """Raised when state data does not satisfy the current state invariant."""

    error_code = "workflow_state_invariant_failed"


class ClarificationRequiredError(WorkflowError):
    """Raised when a question cannot safely proceed without clarification."""

    error_code = "clarification_required"


class UnsupportedQuestionError(WorkflowError):
    """Raised when a question is outside the supported query contract."""

    error_code = "unsupported_question"


class ImpossibleQuestionError(WorkflowError):
    """Raised when a question cannot be answered from the configured source."""

    error_code = "impossible_question"
