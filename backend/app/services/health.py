"""Health state assembly without performing database or model work."""

from __future__ import annotations

from collections.abc import Iterable

from app.config import ConfigurationIssue, Settings
from app.models.health import HealthComponent, HealthResponse


def build_health_response(settings: Settings) -> HealthResponse:
    """Build a safe foundation health response from configuration state."""

    issues = settings.configuration_issues()
    source_database = _database_component(
        settings.source_database_url is not None
        and bool(settings.source_database_url.get_secret_value().strip()),
        "SOURCE_DATABASE_URL",
        issues,
    )
    index_database = _database_component(
        settings.index_database_url is not None
        and bool(settings.index_database_url.get_secret_value().strip()),
        "INDEX_DATABASE_URL",
        issues,
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
) -> HealthComponent:
    return _configured_component(
        configured,
        field,
        issues,
        configured_detail=(
            "Connection settings are present; connectivity is not checked by the foundation."
        ),
        missing_detail="Connection settings are not configured.",
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
