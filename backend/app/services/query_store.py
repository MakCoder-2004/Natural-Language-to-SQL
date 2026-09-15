"""Application-scoped storage for current-session query workflow state."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from app.workflow.errors import WorkflowError
from app.workflow.state import QueryWorkflowState


class QueryNotFoundError(WorkflowError):
    """Raised when a query ID is not present in the current application session."""

    error_code = "query_not_found"


class QueryStore:
    """Thread-safe in-memory store for immutable query states."""

    def __init__(self) -> None:
        self._states: dict[UUID, QueryWorkflowState] = {}
        self._lock = RLock()

    def get(self, query_id: UUID) -> QueryWorkflowState | None:
        with self._lock:
            return self._states.get(query_id)

    def require(self, query_id: UUID) -> QueryWorkflowState:
        state = self.get(query_id)
        if state is None:
            raise QueryNotFoundError("The requested query was not found in this session.")
        return state

    def put(self, state: QueryWorkflowState) -> QueryWorkflowState:
        with self._lock:
            self._states[state.query_id] = state
        return state

    def clear(self) -> None:
        with self._lock:
            self._states.clear()
