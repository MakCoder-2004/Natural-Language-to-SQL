from __future__ import annotations

from typing import Any

from app.config import Settings
from app.database.services import DatabaseServices
from app.main import create_app
from app.models.query import QueryRequest
from app.models.sql import SqlProposal, SqlValidationResult
from app.services.query_service import QueryService
from app.workflow.errors import WorkflowError
from app.workflow.state import QueryState, QueryWorkflowState
from fastapi.testclient import TestClient


def _state(*, status: QueryState = QueryState.READY_FOR_REVIEW) -> QueryWorkflowState:
    request = QueryRequest.create("How many records exist?")
    proposal = SqlProposal.create(sql="SELECT 1", interpretation="Counts records.")
    validation = SqlValidationResult(
        True,
        proposal.sql,
        proposal.sql_hash,
        (),
        (),
        (),
        (),
        (),
        (),
        True,
        True,
    )
    return QueryWorkflowState(
        query_id=request.query_id,
        pipeline_run_id=request.pipeline_run_id,
        question=request.question,
        state=status,
        proposal=proposal,
        original_proposal=proposal,
        validation=validation,
        validated_sql_hash=proposal.sql_hash,
    )


class _Workflow:
    def __init__(self) -> None:
        self.state = _state()

    def run(self, question: str, *, execution_mode: str = "REVIEW") -> QueryWorkflowState:
        self.state = self.state.evolve(question=question, execution_mode=execution_mode)
        return self.state

    def resume_clarification(
        self, state: QueryWorkflowState, clarification: str
    ) -> QueryWorkflowState:
        return state

    def edit_sql(self, state: QueryWorkflowState, sql: str) -> QueryWorkflowState:
        return state

    def approve(
        self, state: QueryWorkflowState, *, sql_version: str | None = None
    ) -> QueryWorkflowState:
        if sql_version != state.validated_sql_hash:
            raise WorkflowError("The supplied SQL version is stale.")
        return state.evolve(state=QueryState.APPROVED, approval_sql_hash=sql_version)

    def execute_approved(self, state: QueryWorkflowState) -> QueryWorkflowState:
        return state.evolve(state=QueryState.COMPLETED)

    def regenerate(self, state: QueryWorkflowState) -> QueryWorkflowState:
        return state


def _client(workflow: Any | None = None) -> TestClient:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    service = QueryService(settings, None, workflow=workflow or _Workflow())
    app = create_app(settings, DatabaseServices(), service)
    return TestClient(app)


def test_query_lifecycle_returns_backend_owned_ids_and_inspector() -> None:
    with _client() as client:
        response = client.post("/api/query", json={"question": "How many records exist?"})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "READY_FOR_REVIEW"
        assert body["execution_mode"] == "REVIEW"
        assert body["sql_inspector"]["sql"] == "SELECT 1"
        assert body["sql_inspector"]["sql_version"]
        assert body["query_id"]


def test_query_requests_reject_client_authorization_fields() -> None:
    with _client() as client:
        response = client.post(
            "/api/query",
            json={
                "question": "How many records exist?",
                "validated": True,
                "approved": True,
            },
        )

        assert response.status_code == 422


def test_unknown_query_id_is_not_found_without_internal_details() -> None:
    with _client() as client:
        response = client.get("/api/query/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "query_not_found"
        assert "Traceback" not in response.text


def test_approval_requires_backend_sql_version_and_execute_returns_completion() -> None:
    workflow = _Workflow()
    with _client(workflow) as client:
        created = client.post("/api/query", json={"question": "How many records exist?"}).json()
        query_id = created["query_id"]
        version = created["sql_inspector"]["sql_version"]

        stale = client.post(f"/api/query/{query_id}/approve", json={"sql_version": "stale"})
        assert stale.status_code == 409

        approved = client.post(f"/api/query/{query_id}/approve", json={"sql_version": version})
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"

        executed = client.post(f"/api/query/{query_id}/execute")
        assert executed.status_code == 200
        assert executed.json()["status"] == "COMPLETED"


def test_cors_allows_configured_frontend_post_preflight() -> None:
    with _client() as client:
        response = client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
