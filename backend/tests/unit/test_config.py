from typing import Any, cast

import pytest
from app.config import ConfigurationError, Settings
from pydantic import ValidationError

VALID_VALUES = {
    "source_database_url": "postgresql+psycopg://source_user:source_password@source-host:5432/source_db",
    "index_database_url": "postgresql+psycopg://index_user:index_password@index-host:5432/index_db",
    "openrouter_api_key": "test-key",
    "question_model": "question-model",
    "sql_model": "sql-model",
    "sql_correction_model": "sql-correction-model",
    "answer_model": "answer-model",
    "embedding_model": "embedding-model",
    "source_schema_scope": "analytics,reporting",
}


def make_settings(**overrides: object) -> Settings:
    values = {**VALID_VALUES, **overrides}
    settings_constructor: Any = Settings
    return cast(Settings, settings_constructor(_env_file=None, **values))


def test_valid_settings_parse_schema_scope_and_model_roles() -> None:
    settings = make_settings(source_schema_scope=" analytics, reporting ")

    assert settings.source_schema_names == ("analytics", "reporting")
    assert [role for role, _ in settings.model_roles] == [
        "QUESTION_MODEL",
        "SQL_MODEL",
        "SQL_CORRECTION_MODEL",
        "ANSWER_MODEL",
        "EMBEDDING_MODEL",
    ]
    assert settings.configuration_issues() == ()


def test_missing_values_are_reported_without_secret_values() -> None:
    settings_constructor: Any = Settings
    settings = cast(Settings, settings_constructor(_env_file=None))

    issues = settings.configuration_issues()
    fields = {issue.field for issue in issues}
    message = str(ConfigurationError(issues))

    assert "SOURCE_DATABASE_URL" in fields
    assert "INDEX_DATABASE_URL" in fields
    assert "QUESTION_MODEL" in fields
    assert "<password>" not in message
    assert "secret" not in message.lower()


def test_empty_secret_values_are_treated_as_missing() -> None:
    settings = make_settings(source_database_url="", index_database_url="")

    issues = settings.configuration_issues()

    assert {issue.code for issue in issues if issue.field.endswith("DATABASE_URL")} == {"missing"}


def test_runtime_validation_can_require_the_openrouter_key() -> None:
    settings = make_settings(openrouter_api_key=None)

    with pytest.raises(ConfigurationError) as raised:
        settings.validate_for_runtime()

    assert any(issue.field == "OPENROUTER_API_KEY" for issue in raised.value.issues)
    assert "test-key" not in str(raised.value)


def test_schema_scope_rejects_system_schemas() -> None:
    settings = make_settings(source_schema_scope="analytics,pg_catalog")

    assert any(
        issue.field == "SOURCE_SCHEMA_SCOPE" and issue.code == "system_schema"
        for issue in settings.configuration_issues()
    )


def test_source_and_index_urls_must_be_distinct() -> None:
    settings = make_settings(index_database_url=VALID_VALUES["source_database_url"])

    assert any(issue.code == "same_database" for issue in settings.configuration_issues())


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_correction_retries", 3),
        ("max_returned_rows", 0),
        ("max_result_bytes", -1),
        ("query_timeout_seconds", 0),
        ("database_connect_timeout_seconds", 0),
        ("source_pool_timeout_seconds", 0),
        ("source_pool_recycle_seconds", 0),
        ("index_pool_timeout_seconds", 0),
        ("index_pool_recycle_seconds", 0),
        ("source_pool_size", -1),
        ("source_max_overflow", -1),
        ("index_pool_size", -1),
        ("index_max_overflow", -1),
        ("retrieval_vector_candidate_limit", 257),
        ("retrieval_max_selected_tables", 257),
        ("retrieval_max_relationship_hops", 2),
        ("retrieval_max_context_characters", 100_001),
    ],
)
def test_limits_are_bounded(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


def test_non_postgres_urls_are_rejected() -> None:
    settings = make_settings(source_database_url="https://not-a-database.example")

    assert any(
        issue.field == "SOURCE_DATABASE_URL" and issue.code == "invalid_url"
        for issue in settings.configuration_issues()
    )


def test_secret_values_are_masked_by_pydantic() -> None:
    settings = make_settings()

    assert "source_password" not in repr(settings)
    assert "test-key" not in repr(settings)


def test_schema_scope_removes_duplicate_names_without_reordering() -> None:
    settings = make_settings(source_schema_scope="analytics, reporting, analytics")

    assert settings.source_schema_names == ("analytics", "reporting")


@pytest.mark.parametrize(
    "field,value",
    [
        ("retrieval_min_vector_similarity", -0.1),
        ("retrieval_min_vector_similarity", 1.1),
        ("retrieval_vector_weight", 0.0),
        ("retrieval_keyword_weight", -0.1),
    ],
)
def test_retrieval_scores_are_bounded(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})
