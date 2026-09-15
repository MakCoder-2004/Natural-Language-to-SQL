"""FastAPI routes for single-user runtime database settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_query_service, get_runtime_database_manager
from app.api.errors import error_response
from app.api.schemas import (
    DatabaseConnectionRequest,
    DatabaseConnectionResponse,
    DatabaseIndexResponse,
)
from app.services.indexing_service import IndexingService
from app.services.query_service import QueryService
from app.services.runtime_database import RuntimeDatabaseManager

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.post("/database/test", response_model=DatabaseConnectionResponse)
def test_database(
    request: DatabaseConnectionRequest,
    manager: Annotated[RuntimeDatabaseManager, Depends(get_runtime_database_manager)],
) -> DatabaseConnectionResponse | JSONResponse:
    try:
        return DatabaseConnectionResponse.from_profile(
            manager.test(request.url, request.schema_scope)
        )
    except Exception as exc:
        return error_response(exc)


@router.post("/database", response_model=DatabaseConnectionResponse)
def save_database(
    request: DatabaseConnectionRequest,
    manager: Annotated[RuntimeDatabaseManager, Depends(get_runtime_database_manager)],
    query_service: Annotated[QueryService, Depends(get_query_service)],
) -> DatabaseConnectionResponse | JSONResponse:
    try:
        response = DatabaseConnectionResponse.from_profile(
            manager.save(request.url, request.schema_scope)
        )
        query_service.reset_after_source_change()
        return response
    except Exception as exc:
        return error_response(exc)


@router.delete("/database", response_model=None)
def disconnect_database(
    manager: Annotated[RuntimeDatabaseManager, Depends(get_runtime_database_manager)],
    query_service: Annotated[QueryService, Depends(get_query_service)],
) -> None | JSONResponse:
    try:
        manager.disconnect()
        query_service.reset_after_source_change()
        return None
    except Exception as exc:
        return error_response(exc)


@router.post("/database/index", response_model=DatabaseIndexResponse)
def index_database(
    manager: Annotated[RuntimeDatabaseManager, Depends(get_runtime_database_manager)],
) -> DatabaseIndexResponse | JSONResponse:
    try:
        run = IndexingService(manager.settings, manager.services).run()
        return DatabaseIndexResponse(
            status=run.status,
            source_fingerprint=run.source_fingerprint,
            document_count=run.document_count,
            embedding_count=run.embedding_count,
            indexed_at=run.finished_at,
        )
    except Exception as exc:
        return error_response(exc)
