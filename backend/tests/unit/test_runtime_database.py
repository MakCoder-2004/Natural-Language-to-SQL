from __future__ import annotations

import pytest
from app.config import Settings
from app.database.errors import DatabasePermissionError, DatabaseServiceError
from app.database.services import DatabaseServices
from app.services.runtime_database import RuntimeDatabaseManager


def _manager() -> RuntimeDatabaseManager:
    return RuntimeDatabaseManager(Settings(_env_file=None), DatabaseServices())  # type: ignore[call-arg]


def test_runtime_source_rejects_the_local_index_host() -> None:
    with pytest.raises(DatabasePermissionError, match="local schema index"):
        _manager()._candidate(
            "postgresql+psycopg://user:password@index-db:5432/schema_index", "public"
        )


def test_runtime_source_requires_a_postgresql_url_and_schema() -> None:
    with pytest.raises(DatabaseServiceError, match="must use PostgreSQL"):
        _manager()._candidate("mysql://user:password@db:3306/analytics", "public")
    with pytest.raises(DatabaseServiceError, match="source schema"):
        _manager()._candidate("postgresql+psycopg://user:password@db:5432/analytics", " ")


def test_disconnect_clears_the_runtime_source_binding() -> None:
    manager = _manager()
    manager.disconnect()

    assert manager.services.source is None
    assert manager.settings.source_database_url is None
