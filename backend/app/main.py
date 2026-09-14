"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.config import Settings, get_settings
from app.database.errors import DatabaseServiceError
from app.database.services import DatabaseServices, create_database_services

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
    settings: Settings | None = None, database_services: DatabaseServices | None = None
) -> FastAPI:
    """Create the FastAPI application with optional test settings."""

    resolved_settings = settings if settings is not None else get_settings()
    application = FastAPI(
        title="Safe Schema-aware SQL Analytics API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
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
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    return application


app = create_app()
