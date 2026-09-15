"""Application service exposing the query workflow across HTTP requests."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any
from uuid import UUID

from app.config import Settings
from app.database.services import DatabaseServices
from app.services.query_store import QueryStore
from app.workflow.graph import DeterministicQueryWorkflow
from app.workflow.state import ExecutionMode, QueryWorkflowState

WorkflowFactory = Callable[[Settings, DatabaseServices | None], DeterministicQueryWorkflow]


class QueryService:
    """Coordinate stored immutable workflow states without owning HTTP concerns."""

    def __init__(
        self,
        settings: Settings,
        database_services: DatabaseServices | None,
        *,
        store: QueryStore | None = None,
        workflow: Any | None = None,
        workflow_factory: WorkflowFactory | None = None,
    ) -> None:
        self._settings = settings
        self._database_services = database_services
        self._workflow_factory = workflow_factory or DeterministicQueryWorkflow
        self.store = store or QueryStore()
        self._workflow = workflow
        self._lock = RLock()

    @property
    def workflow(self) -> DeterministicQueryWorkflow:
        """Create model-backed workflow dependencies only when a query is submitted."""

        if self._workflow is None:
            self._workflow = self._workflow_factory(self._settings, self._database_services)
        return self._workflow

    def start_query(self, question: str, execution_mode: ExecutionMode) -> QueryWorkflowState:
        with self._lock:
            state = self.workflow.run(question, execution_mode=execution_mode)
            return self.store.put(state)

    def clarify_query(self, query_id: UUID, clarification: str) -> QueryWorkflowState:
        with self._lock:
            state = self.store.require(query_id)
            return self.store.put(self.workflow.resume_clarification(state, clarification))

    def edit_query(self, query_id: UUID, sql: str) -> QueryWorkflowState:
        with self._lock:
            state = self.store.require(query_id)
            return self.store.put(self.workflow.edit_sql(state, sql))

    def approve_query(self, query_id: UUID, sql_version: str) -> QueryWorkflowState:
        with self._lock:
            state = self.store.require(query_id)
            return self.store.put(self.workflow.approve(state, sql_version=sql_version))

    def execute_query(self, query_id: UUID) -> QueryWorkflowState:
        with self._lock:
            state = self.store.require(query_id)
            return self.store.put(self.workflow.execute_approved(state))

    def regenerate_query(self, query_id: UUID) -> QueryWorkflowState:
        with self._lock:
            state = self.store.require(query_id)
            return self.store.put(self.workflow.regenerate(state))

    def get_query(self, query_id: UUID) -> QueryWorkflowState:
        return self.store.require(query_id)

    def reset_after_source_change(self) -> None:
        """Drop cached workflows and query states after changing databases."""

        with self._lock:
            self._workflow = None
            self.store.clear()
