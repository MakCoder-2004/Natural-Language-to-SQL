"""Safe mapping from application errors to HTTP responses."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.database.errors import (
    DatabasePermissionError,
    DatabaseUnavailableError,
    IndexReadinessError,
    ModelServiceError,
    NoRelevantSchemaError,
    QueryExecutionError,
    QueryTimeoutError,
    QueryValidationError,
)
from app.services.query_store import QueryNotFoundError
from app.workflow.errors import WorkflowError


def error_response(
    error: Exception,
    *,
    query_id: str | None = None,
) -> JSONResponse:
    """Return a stable, non-sensitive error response for a known domain error."""

    code = getattr(error, "error_code", "internal_error")
    status = 500
    if isinstance(error, QueryNotFoundError):
        status = 404
    elif isinstance(error, (DatabaseUnavailableError, IndexReadinessError)):
        status = 503
    elif isinstance(error, QueryTimeoutError):
        status = 504
    elif isinstance(error, (DatabasePermissionError, QueryExecutionError)):
        status = 502
    elif isinstance(error, NoRelevantSchemaError):
        status = 422
    elif isinstance(error, QueryValidationError):
        status = 422
    elif isinstance(error, ModelServiceError):
        status = 502
    elif isinstance(error, WorkflowError):
        status = 409

    message = str(error) if isinstance(error, WorkflowError) else _safe_message(code)
    payload: dict[str, object] = {
        "error": {"code": code, "message": message, "details": {}},
    }
    if query_id is not None:
        payload["query_id"] = query_id
    return JSONResponse(status_code=status, content=payload)


def _safe_message(code: str) -> str:
    messages = {
        "database_unavailable": "The source database is currently unavailable.",
        "database_permission_denied": "The configured database role lacks required access.",
        "index_not_ready": "The schema index is not ready for queries.",
        "query_timeout": "The source query exceeded the configured time limit.",
        "query_execution_error": "The source query could not be completed.",
        "no_relevant_schema": "No relevant source schema was found for this question.",
        "query_validation_error": "The SQL statement was rejected by the safety policy.",
        "model_error": "The configured model service could not complete the request.",
        "internal_error": "The request could not be completed safely.",
    }
    return messages.get(code, "The request could not be completed safely.")
