"""Types shared by disposable PostgreSQL integration fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.config import Settings
from pydantic import SecretStr
from sqlalchemy.engine import URL


@dataclass(frozen=True, slots=True)
class PostgresIntegrationFixture:
    """Connection details for separate source and index test databases."""

    source_url: URL
    index_url: URL
    source_database_name: str
    index_database_name: str


def fixture_settings(fixture: PostgresIntegrationFixture) -> Settings:
    """Build backend settings for the disposable integration databases."""

    settings_constructor: Any = Settings
    return cast(
        Settings,
        settings_constructor(
            _env_file=None,
            source_database_url=SecretStr(fixture.source_url.render_as_string(hide_password=False)),
            index_database_url=SecretStr(fixture.index_url.render_as_string(hide_password=False)),
            source_schema_scope="analytics,reporting",
            database_connect_timeout_seconds=5,
            query_timeout_seconds=1,
            openrouter_api_key=SecretStr("test-key"),
            question_model="question-model",
            sql_model="sql-model",
            sql_correction_model="sql-correction-model",
            answer_model="answer-model",
            embedding_model="embedding-model",
        ),
    )
