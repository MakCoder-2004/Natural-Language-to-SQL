"""FastAPI routes for the query lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_query_service
from app.api.errors import error_response
from app.api.schemas import (
    ApprovalRequest,
    ClarificationRequest,
    QueryCreateRequest,
    QueryResponse,
    SqlEditRequest,
    query_response_from_state,
)
from app.services.query_service import QueryService
from app.workflow.state import QueryWorkflowState

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post(
    "", response_model=QueryResponse, responses={400: {"model": dict}, 503: {"model": dict}}
)
def create_query(
    request: QueryCreateRequest,
    service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryResponse | JSONResponse:
    try:
        state = service.start_query(request.question, request.execution_mode)
    except Exception as exc:
        return error_response(exc)
    return query_response_from_state(state)


@router.post("/{query_id}/clarify", response_model=QueryResponse)
def clarify_query(
    query_id: UUID,
    request: ClarificationRequest,
    service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryResponse | JSONResponse:
    return _run(lambda: service.clarify_query(query_id, request.clarification), query_id)


@router.post("/{query_id}/edit", response_model=QueryResponse)
def edit_query(
    query_id: UUID,
    request: SqlEditRequest,
    service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryResponse | JSONResponse:
    return _run(lambda: service.edit_query(query_id, request.sql), query_id)


@router.post("/{query_id}/approve", response_model=QueryResponse)
def approve_query(
    query_id: UUID,
    request: ApprovalRequest,
    service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryResponse | JSONResponse:
    return _run(lambda: service.approve_query(query_id, request.sql_version), query_id)


@router.post("/{query_id}/execute", response_model=QueryResponse)
def execute_query(
    query_id: UUID, service: Annotated[QueryService, Depends(get_query_service)]
) -> QueryResponse | JSONResponse:
    return _run(lambda: service.execute_query(query_id), query_id)


@router.post("/{query_id}/regenerate", response_model=QueryResponse)
def regenerate_query(
    query_id: UUID, service: Annotated[QueryService, Depends(get_query_service)]
) -> QueryResponse | JSONResponse:
    return _run(lambda: service.regenerate_query(query_id), query_id)


@router.get("/{query_id}", response_model=QueryResponse)
def get_query(
    query_id: UUID, service: Annotated[QueryService, Depends(get_query_service)]
) -> QueryResponse | JSONResponse:
    return _run(lambda: service.get_query(query_id), query_id)


def _run(
    operation: Callable[[], QueryWorkflowState], query_id: UUID
) -> QueryResponse | JSONResponse:
    try:
        state = operation()
    except Exception as exc:
        return error_response(exc, query_id=str(query_id))
    return query_response_from_state(state)
