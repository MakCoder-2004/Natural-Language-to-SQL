from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import SecretStr


def valid_settings() -> Settings:
    return Settings(
        source_database_url=SecretStr(
            "postgresql+psycopg://source_user:source_password@source-host:5432/source_db"
        ),
        index_database_url=SecretStr(
            "postgresql+psycopg://index_user:index_password@index-host:5432/index_db"
        ),
        openrouter_api_key=SecretStr("test-key"),
        question_model="question-model",
        sql_model="sql-model",
        sql_correction_model="sql-correction-model",
        answer_model="answer-model",
        embedding_model="embedding-model",
        source_schema_scope="analytics",
    )


def test_health_reports_foundation_state_without_secrets() -> None:
    with TestClient(create_app(valid_settings())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["service"]["status"] == "ok"
    assert payload["source_database"]["status"] == "configured"
    assert payload["index_database"]["status"] == "configured"
    assert payload["schema_index"]["status"] == "not_initialized"
    assert payload["openrouter"]["status"] == "configured"
    assert payload["configuration_errors"] == []
    assert "source_password" not in response.text
    assert "test-key" not in response.text
    assert "postgresql+psycopg" not in response.text


def test_health_reports_missing_configuration_actionably() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["source_database"]["status"] == "not_configured"
    assert payload["index_database"]["status"] == "not_configured"
    assert payload["openrouter"]["status"] == "not_configured"
    assert any("SOURCE_DATABASE_URL" in error for error in payload["configuration_errors"])
    assert any("INDEX_DATABASE_URL" in error for error in payload["configuration_errors"])
    assert "postgresql" not in response.text
