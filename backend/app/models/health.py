"""Public health response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

HealthStatus = Literal[
    "ok",
    "configured",
    "not_configured",
    "not_checked",
    "not_initialized",
    "invalid",
]


class HealthComponent(BaseModel):
    """Safe status for one application component."""

    model_config = ConfigDict(extra="forbid")

    status: HealthStatus
    configured: bool
    detail: str


class HealthResponse(BaseModel):
    """Health information that never includes credentials or connection URLs."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "degraded"]
    service: HealthComponent
    source_database: HealthComponent
    index_database: HealthComponent
    schema_index: HealthComponent
    openrouter: HealthComponent
    configuration_errors: list[str]
