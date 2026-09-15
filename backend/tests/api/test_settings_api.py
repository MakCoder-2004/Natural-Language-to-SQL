from __future__ import annotations

from app.config import Settings
from app.database.services import DatabaseServices
from app.main import create_app
from fastapi.testclient import TestClient


def test_settings_rejects_non_postgres_urls_without_leaking_input() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    with TestClient(create_app(settings, DatabaseServices())) as client:
        response = client.post(
            "/api/settings/database/test",
            json={"url": "mysql://user:password@db/analytics", "schema_scope": "public"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "The request could not be completed safely."
    assert "password" not in response.text


def test_settings_rejects_client_connection_metadata_fields() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    with TestClient(create_app(settings, DatabaseServices())) as client:
        response = client.post(
            "/api/settings/database/test",
            json={
                "url": "postgresql+psycopg://user:password@db/analytics",
                "schema_scope": "public",
                "read_only_verified": True,
            },
        )

    assert response.status_code == 422


def test_schema_discovery_accepts_only_postgres_urls() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    with TestClient(create_app(settings, DatabaseServices())) as client:
        response = client.post(
            "/api/settings/database/discover",
            json={"url": "mysql://user:password@db/analytics"},
        )

    assert response.status_code == 422
    assert "password" not in response.text
