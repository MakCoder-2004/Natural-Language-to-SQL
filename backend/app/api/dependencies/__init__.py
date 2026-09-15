"""FastAPI dependency providers for backend-owned services."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.config import Settings
from app.database.services import DatabaseServices
from app.services.query_service import QueryService
from app.services.runtime_database import RuntimeDatabaseManager


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database_services(request: Request) -> DatabaseServices:
    return cast(DatabaseServices, request.app.state.database_services)


def get_query_service(request: Request) -> QueryService:
    return cast(QueryService, request.app.state.query_service)


def get_runtime_database_manager(request: Request) -> RuntimeDatabaseManager:
    return cast(RuntimeDatabaseManager, request.app.state.runtime_database_manager)
