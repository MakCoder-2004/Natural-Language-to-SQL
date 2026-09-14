"""Health endpoint."""

from typing import cast

from fastapi import APIRouter, Request

from app.config import Settings
from app.database.services import DatabaseServices
from app.models.health import HealthResponse
from app.services.health import build_health_response

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Return process, configuration, and foundation dependency state."""

    settings = cast(Settings, request.app.state.settings)
    database_services = cast(
        DatabaseServices | None, getattr(request.app.state, "database_services", None)
    )
    return build_health_response(settings, database_services)
