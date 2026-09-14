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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Validate configuration at startup without logging secret values."""

    settings = cast(Settings, application.state.settings)
    application.state.settings = settings
    issues = settings.configuration_issues()
    if issues:
        logger.warning(
            "startup_configuration_invalid fields=%s issue_count=%d",
            sorted({issue.field for issue in issues}),
            len(issues),
        )
    else:
        logger.info("startup_configuration_valid")
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application with optional test settings."""

    resolved_settings = settings if settings is not None else get_settings()
    application = FastAPI(
        title="Safe Schema-aware SQL Analytics API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
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
