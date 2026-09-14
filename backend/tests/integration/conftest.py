from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from testcontainers.community.postgres import PostgresContainer

from tests.fixtures.postgres import PostgresIntegrationFixture

ADMIN_USERNAME = "postgres"
ADMIN_PASSWORD = "admin-password"
READER_USERNAME = "source_reader"
READER_PASSWORD = "reader-password"
SOURCE_DATABASE = "source_fixture"
INDEX_DATABASE = "index_fixture"


@pytest.fixture(scope="session")
def postgres_fixture() -> Iterator[PostgresIntegrationFixture]:
    with (
        PostgresContainer(
            image="pgvector/pgvector:pg16",
            username=ADMIN_USERNAME,
            password=ADMIN_PASSWORD,
            dbname=SOURCE_DATABASE,
        ) as source_container,
        PostgresContainer(
            image="pgvector/pgvector:pg16",
            username=ADMIN_USERNAME,
            password=ADMIN_PASSWORD,
            dbname=INDEX_DATABASE,
        ) as index_container,
    ):
        source_admin_url = _container_url(
            source_container, SOURCE_DATABASE, ADMIN_USERNAME, ADMIN_PASSWORD
        )
        index_url = _container_url(index_container, INDEX_DATABASE, ADMIN_USERNAME, ADMIN_PASSWORD)
        _initialize_source_database(source_admin_url)
        source_reader_url = _container_url(
            source_container, SOURCE_DATABASE, READER_USERNAME, READER_PASSWORD
        )
        yield PostgresIntegrationFixture(
            source_url=source_reader_url,
            index_url=index_url,
            source_database_name=SOURCE_DATABASE,
            index_database_name=INDEX_DATABASE,
        )


def _container_url(
    container: PostgresContainer,
    database: str,
    username: str,
    password: str,
) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=container.get_container_host_ip(),
        port=int(container.get_exposed_port(5432)),
        database=database,
    )


def _initialize_source_database(admin_url: URL) -> None:
    engine = create_engine(admin_url)
    statements = [
        "CREATE ROLE source_reader LOGIN PASSWORD 'reader-password'",
        "ALTER ROLE source_reader WITH LOGIN PASSWORD 'reader-password'",
        "CREATE SCHEMA analytics",
        "CREATE SCHEMA reporting",
        "CREATE SCHEMA internal",
        """
        CREATE TABLE analytics.accounts (
            account_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            external_code text NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE analytics.account_profiles (
            account_id integer PRIMARY KEY REFERENCES analytics.accounts(account_id),
            display_name text
        )
        """,
        """
        CREATE TABLE analytics.events (
            event_id bigint PRIMARY KEY,
            account_id integer NOT NULL REFERENCES analytics.accounts(account_id) ON DELETE CASCADE,
            occurred_at timestamptz,
            event_name text
        )
        """,
        """
        CREATE UNIQUE INDEX events_account_time_idx
        ON analytics.events (account_id ASC, occurred_at DESC NULLS LAST)
        INCLUDE (event_name)
        """,
        """
        CREATE VIEW reporting.account_event_counts AS
        SELECT account_id, count(*) AS event_count
        FROM analytics.events
        GROUP BY account_id
        """,
        "CREATE TABLE internal.not_in_scope (secret_value text)",
        "COMMENT ON SCHEMA analytics IS 'Approved analytics schema'",
        "COMMENT ON TABLE analytics.accounts IS 'Accounts available for analytics'",
        (
            "COMMENT ON COLUMN analytics.accounts.external_code "
            "IS 'Stable external account identifier'"
        ),
        "GRANT USAGE ON SCHEMA analytics, reporting TO source_reader",
        "GRANT SELECT ON ALL TABLES IN SCHEMA analytics, reporting TO source_reader",
        "GRANT CONNECT ON DATABASE source_fixture TO source_reader",
        "REVOKE CREATE ON SCHEMA analytics, reporting FROM PUBLIC",
        "REVOKE CREATE ON DATABASE source_fixture FROM PUBLIC",
    ]
    try:
        with engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
    finally:
        engine.dispose()
