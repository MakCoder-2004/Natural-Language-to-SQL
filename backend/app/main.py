"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import cast

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router
from app.api.routes.settings import router as settings_router
from app.config import Settings, get_settings
from app.database.errors import DatabaseServiceError
from app.database.services import DatabaseServices, create_database_services
from app.services.query_service import QueryService
from app.services.runtime_database import RuntimeDatabaseManager
from app.telemetry import emit_event

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Validate configuration at startup without logging secret values."""

    settings = cast(Settings, application.state.settings)
    application.state.settings = settings
    database_services = cast(
        DatabaseServices | None, getattr(application.state, "database_services", None)
    )
    if database_services is None:
        try:
            database_services = create_database_services(settings)
        except DatabaseServiceError as exc:
            logger.warning("database_services_unavailable error_code=%s", type(exc).__name__)
            database_services = DatabaseServices()
    application.state.database_services = database_services
    application.state.runtime_database_manager = RuntimeDatabaseManager(settings, database_services)
    if getattr(application.state, "query_service", None) is None:
        application.state.query_service = QueryService(settings, database_services)
    issues = settings.configuration_issues()
    if issues:
        logger.warning(
            "startup_configuration_invalid fields=%s issue_count=%d",
            sorted({issue.field for issue in issues}),
            len(issues),
        )
    else:
        logger.info("startup_configuration_valid")
    try:
        yield
    finally:
        database_services.dispose()


def create_app(
    settings: Settings | None = None,
    database_services: DatabaseServices | None = None,
    query_service: QueryService | None = None,
) -> FastAPI:
    """Create the FastAPI application with optional test settings."""

    resolved_settings = settings if settings is not None else get_settings()
    application = FastAPI(
        title="Safe Schema-aware SQL Analytics API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.query_service = query_service
    if database_services is not None:
        application.state.database_services = database_services
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in resolved_settings.frontend_origins.split(",")
            if origin.strip()
        ],
        allow_credentials=False,
        allow_methods=["DELETE", "GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(query_router)
    application.include_router(settings_router)

    @application.middleware("http")
    async def request_telemetry(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = perf_counter()
        response = await call_next(request)
        emit_event(
            logger,
            "http_request_completed",
            method=getattr(request, "method", ""),
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        return response

    return application


app = create_app()
