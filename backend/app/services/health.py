"""Health state assembly without performing database or model work."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text

from app.config import ConfigurationIssue, Settings
from app.database.errors import DatabasePermissionError, DatabaseUnavailableError
from app.database.index_connection import IndexDatabase
from app.database.services import DatabaseServices
from app.database.source_connection import SourceDatabase
from app.database.source_permissions import verify_source_read_only_access
from app.models.health import HealthComponent, HealthResponse


def build_health_response(
    settings: Settings, database_services: DatabaseServices | None = None
) -> HealthResponse:
    """Build a safe health response from configuration and bounded database probes."""

    issues = settings.configuration_issues()
    source_database = _database_component(
        settings.source_database_url is not None
        and bool(settings.source_database_url.get_secret_value().strip()),
        "SOURCE_DATABASE_URL",
        issues,
        database_services.source if database_services is not None else None,
        verify_read_only=True,
    )
    index_database = _database_component(
        settings.index_database_url is not None
        and bool(settings.index_database_url.get_secret_value().strip()),
        "INDEX_DATABASE_URL",
        issues,
        database_services.index if database_services is not None else None,
    )
    openrouter = _configured_component(
        settings.openrouter_api_key is not None
        and bool(settings.openrouter_api_key.get_secret_value().strip()),
        "OPENROUTER_API_KEY",
        issues,
        configured_detail="OpenRouter credentials are configured on the backend.",
        missing_detail="OpenRouter credentials are not configured.",
    )

    return HealthResponse(
        status="degraded",
        service=HealthComponent(
            status="ok",
            configured=True,
            detail="FastAPI is available.",
        ),
        source_database=source_database,
        index_database=index_database,
        schema_index=HealthComponent(
            status="not_initialized",
            configured=index_database.configured,
            detail="Schema-index initialization belongs to a later milestone.",
        ),
        openrouter=openrouter,
        configuration_errors=[issue.message for issue in issues],
    )


def _database_component(
    configured: bool,
    field: str,
    issues: Iterable[ConfigurationIssue],
    database: SourceDatabase | IndexDatabase | None,
    *,
    verify_read_only: bool = False,
) -> HealthComponent:
    component = _configured_component(
        configured,
        field,
        issues,
        configured_detail=(
            "Connection settings are present; connectivity is not checked by the foundation."
        ),
        missing_detail="Connection settings are not configured.",
    )
    if not configured or database is None or component.status != "configured":
        return component

    try:
        if verify_read_only:
            if not isinstance(database, SourceDatabase):
                return HealthComponent(
                    status="permission_denied",
                    configured=True,
                    detail="The source health dependency is invalid.",
                    reachable=False,
                    read_only_verified=False,
                )
            verify_source_read_only_access(database)
            return HealthComponent(
                status="reachable",
                configured=True,
                detail="Source database is reachable and read-only access is verified.",
                reachable=True,
                read_only_verified=True,
            )
        if not isinstance(database, IndexDatabase):
            return HealthComponent(
                status="unavailable",
                configured=True,
                detail=f"{field} health dependency is unavailable.",
                reachable=False,
            )
        with database.connect() as connection:
            connection.execute(text("SELECT 1"))
    except DatabasePermissionError:
        return HealthComponent(
            status="permission_denied",
            configured=True,
            detail=f"{field} is reachable but the configured role is not authorized.",
            reachable=True,
            read_only_verified=False if verify_read_only else None,
        )
    except DatabaseUnavailableError:
        return HealthComponent(
            status="unavailable",
            configured=True,
            detail=f"{field} could not be reached.",
            reachable=False,
            read_only_verified=False if verify_read_only else None,
        )
    return HealthComponent(
        status="reachable",
        configured=True,
        detail=f"{field} is reachable.",
        reachable=True,
        read_only_verified=None,
    )


def _configured_component(
    configured: bool,
    field: str,
    issues: Iterable[ConfigurationIssue],
    *,
    configured_detail: str,
    missing_detail: str,
) -> HealthComponent:
    field_issues = tuple(issue for issue in issues if issue.field == field)
    if any(issue.code == "invalid_url" for issue in field_issues):
        return HealthComponent(
            status="invalid",
            configured=False,
            detail=f"{field} is invalid.",
        )
    if not configured:
        return HealthComponent(
            status="not_configured",
            configured=False,
            detail=missing_detail,
        )
    return HealthComponent(
        status="configured",
        configured=True,
        detail=configured_detail,
    )
