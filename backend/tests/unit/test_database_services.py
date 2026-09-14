from typing import Any, cast

import pytest
from app.config import Settings
from app.database.engine import create_database_engine, parse_postgres_url
from app.database.errors import DatabaseSeparationError, DatabaseServiceError
from app.database.index_connection import IndexDatabase
from app.database.services import create_database_services
from app.database.source_connection import SourceDatabase
from app.database.source_execution import SourceExecutionBinding
from pydantic import SecretStr
from sqlalchemy.engine import URL


def settings() -> Settings:
    settings_constructor: Any = Settings
    return cast(
        Settings,
        settings_constructor(
            _env_file=None,
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
            source_schema_scope="analytics,reporting",
        ),
    )


def test_database_urls_are_parsed_as_postgres_without_exposing_secrets() -> None:
    url = parse_postgres_url(settings().source_database_url, "SOURCE_DATABASE_URL")

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert "source_password" not in repr(DatabaseServiceError("safe"))


def test_non_postgres_database_url_is_rejected() -> None:
    with pytest.raises(DatabaseServiceError, match="SOURCE_DATABASE_URL must be a PostgreSQL URL"):
        parse_postgres_url(SecretStr("https://not-a-database.example"), "SOURCE_DATABASE_URL")


def test_source_and_index_services_are_distinct_and_use_distinct_engines() -> None:
    services = create_database_services(settings())

    assert services.source is not None
    assert services.index is not None
    assert isinstance(services.source, SourceDatabase)
    assert isinstance(services.index, IndexDatabase)
    assert services.source.engine is not services.index.engine
    assert services.source.schema_scope == ("analytics", "reporting")

    services.dispose()


def test_source_execution_binding_rejects_index_database() -> None:
    index = IndexDatabase(
        engine=create_database_engine(
            parse_postgres_url(settings().index_database_url, "INDEX_DATABASE_URL"),
            settings(),
            pool_size=0,
            max_overflow=0,
            pool_timeout=1,
            pool_recycle=1,
        )
    )

    with pytest.raises(DatabaseSeparationError):
        SourceExecutionBinding(cast(SourceDatabase, index))

    index.dispose()
