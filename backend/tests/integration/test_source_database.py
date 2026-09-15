from __future__ import annotations

from typing import Any, cast

import pytest
from app.config import Settings
from app.database.errors import (
    DatabasePermissionError,
    DatabaseSeparationError,
    QueryTimeoutError,
)
from app.database.services import create_database_services
from app.database.source_connection import SourceDatabase, create_source_database
from app.database.source_execution import SourceExecutionBinding
from app.database.source_introspection import SourceIntrospector
from app.database.source_permissions import verify_source_read_only_access
from app.database.source_query import ReadonlySqlExecutor
from app.main import create_app
from app.models.sql import SqlValidationResult, sql_hash
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import URL

from tests.fixtures.postgres import PostgresIntegrationFixture, fixture_settings

pytestmark = pytest.mark.integration


def test_introspection_returns_scoped_technical_metadata(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    database = create_source_database(fixture_settings(postgres_fixture))
    try:
        snapshot = SourceIntrospector(database).introspect()
    finally:
        database.dispose()

    assert snapshot.identity.database_name == postgres_fixture.source_database_name
    assert [schema.name for schema in snapshot.schemas] == ["analytics", "reporting"]
    assert "internal" not in {schema.name for schema in snapshot.schemas}

    analytics = snapshot.schemas[0]
    accounts = next(relation for relation in analytics.relations if relation.name == "accounts")
    events = next(relation for relation in analytics.relations if relation.name == "events")
    view = snapshot.schemas[1].relations[0]

    assert accounts.kind == "table"
    assert accounts.comment == "Accounts available for analytics"
    assert accounts.columns[1].name == "external_code"
    assert accounts.columns[1].nullable is False
    assert accounts.columns[1].comment == "Stable external account identifier"
    assert accounts.primary_key is not None
    assert accounts.primary_key.columns == ("account_id",)
    assert any(
        constraint.columns == ("external_code",) for constraint in accounts.unique_constraints
    )
    assert view.kind == "view"
    assert view.name == "account_event_counts"

    assert len(events.foreign_keys) == 1
    assert events.foreign_keys[0].target_relation == "accounts"
    assert events.foreign_keys[0].cardinality == "many_to_one"
    assert events.indexes
    event_index = next(index for index in events.indexes if index.name == "events_account_time_idx")
    assert [column.name for column in event_index.columns] == ["account_id", "occurred_at"]
    assert event_index.columns[1].sort_order == "desc"
    assert event_index.columns[1].nulls_order == "last"
    assert event_index.included_columns == ("event_name",)


def test_read_only_role_is_verified_and_cannot_write_or_ddl(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    database = create_source_database(fixture_settings(postgres_fixture))
    try:
        snapshot = SourceIntrospector(database).introspect()
        report = verify_source_read_only_access(database, snapshot)
        assert report.identity.database_name == postgres_fixture.source_database_name
        assert report.checked_schema_count == 2
        assert report.checked_relation_count == 4

        with pytest.raises(DatabasePermissionError):
            with database.connect() as connection:
                connection.execute(
                    text("INSERT INTO analytics.accounts (external_code) VALUES ('x')")
                )

        with pytest.raises(DatabasePermissionError):
            with database.connect() as connection:
                connection.execute(text("CREATE TABLE analytics.must_not_exist (id integer)"))
    finally:
        database.dispose()


def test_fingerprint_is_repeatable_and_source_index_connections_are_isolated(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    first_database = create_source_database(settings)
    second_database = create_source_database(settings)
    services = create_database_services(settings)
    try:
        first_snapshot = SourceIntrospector(first_database).introspect()
        second_snapshot = SourceIntrospector(second_database).introspect()
        assert first_snapshot.fingerprint == second_snapshot.fingerprint

        assert services.source is not None
        assert services.index is not None
        langchain_database = services.source.langchain_database("analytics")
        assert langchain_database._engine is services.source.engine
        with pytest.raises(DatabaseSeparationError):
            services.source.langchain_database("internal")
        with services.source.connect() as source_connection:
            source_name = source_connection.execute(text("SELECT current_database()")).scalar_one()
        with services.index.connect() as index_connection:
            index_name = index_connection.execute(text("SELECT current_database()")).scalar_one()
        assert source_name == postgres_fixture.source_database_name
        assert index_name == postgres_fixture.index_database_name
        assert source_name != index_name

        with pytest.raises(DatabaseSeparationError):
            SourceIntrospector(cast(SourceDatabase, services.index))
        with pytest.raises(DatabaseSeparationError):
            SourceExecutionBinding(cast(SourceDatabase, services.index))
        with SourceExecutionBinding(services.source).connect() as execution_connection:
            execution_name = execution_connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
        assert execution_name == source_name
    finally:
        first_database.dispose()
        second_database.dispose()
        services.dispose()


def test_database_timeouts_are_applied_and_health_reports_live_dependencies(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    services = create_database_services(settings)
    assert services.source is not None
    try:
        with services.source.connect() as connection:
            timeout = connection.execute(text("SHOW statement_timeout")).scalar_one()
        assert timeout == "1s"

        with TestClient(create_app(settings, database_services=services)) as client:
            response = client.get("/api/health")

        payload = response.json()
        assert response.status_code == 200
        assert payload["source_database"]["status"] == "reachable"
        assert payload["source_database"]["read_only_verified"] is True
        assert payload["index_database"]["status"] == "reachable"
    finally:
        # TestClient disposes injected services during application shutdown.
        services.dispose()


def test_source_executor_translates_postgres_statement_timeout(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    database = create_source_database(settings)
    try:
        validation = SqlValidationResult(
            passed=True,
            sql="SELECT pg_sleep(2)",
            sql_hash=sql_hash("SELECT pg_sleep(2)"),
            referenced_schemas=(),
            referenced_relations=(),
            referenced_columns=(),
            blocking_errors=(),
            warnings=(),
            applied_limits=(),
            read_only=True,
            single_statement=True,
        )

        with pytest.raises(QueryTimeoutError):
            ReadonlySqlExecutor(settings).execute(SourceExecutionBinding(database), validation)
    finally:
        database.dispose()


def test_connection_and_permission_failures_are_safe(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    wrong_password_url = postgres_fixture.source_url.set(password="wrong-password")
    wrong_settings = _replace_source_url(settings, wrong_password_url)
    database = create_source_database(wrong_settings)
    try:
        with pytest.raises(DatabasePermissionError) as raised:
            SourceIntrospector(database).introspect()
        assert "wrong-password" not in str(raised.value)
        assert "postgresql" not in str(raised.value).lower()
    finally:
        database.dispose()


def _replace_source_url(settings: Settings, source_url: URL) -> Settings:
    values: dict[str, Any] = settings.model_dump()
    values["source_database_url"] = source_url.render_as_string(hide_password=False)
    assert settings.index_database_url is not None
    values["index_database_url"] = settings.index_database_url.get_secret_value()
    settings_constructor: Any = Settings
    return cast(Settings, settings_constructor(_env_file=None, **values))
