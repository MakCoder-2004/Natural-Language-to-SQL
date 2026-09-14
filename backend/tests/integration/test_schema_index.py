from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from app.database.errors import DatabaseSeparationError
from app.database.index_connection import IndexDatabase
from app.database.index_repository import IndexRepository
from app.database.models import SourceSchemaSnapshot
from app.database.services import DatabaseServices, create_database_services
from app.database.source_introspection import SourceIntrospector
from app.models.schema_index import IndexRunRecord, SchemaDocumentBuildResult
from app.retrieval.schema_documents import SchemaDocumentBuilder
from app.retrieval.semantic_metadata import load_semantic_metadata
from sqlalchemy import text

from tests.fixtures.postgres import PostgresIntegrationFixture, fixture_settings

pytestmark = pytest.mark.integration


def test_index_initialization_enables_pgvector_and_reads_vectors(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    services, repository = _fresh_repository(postgres_fixture)
    try:
        with services.index.connect() as connection:  # type: ignore[union-attr]
            extension = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
        assert extension == "vector"

        snapshot = _snapshot(services)
        result = _documents(snapshot)
        run = repository.start_run(
            source_key=result.source_key,
            source_fingerprint=result.source_fingerprint,
            semantic_metadata_digest=result.semantic_metadata_digest,
            document_version=result.document_version,
            embedding_model="test-embedding",
            stale_reference_count=0,
        )
        vectors = _vectors(len(result.documents))
        document_count, embedding_count, dimension = repository.stage_documents(
            run, result.documents, vectors
        )
        promoted = repository.promote_run(run)
        stored = repository.list_active_documents(result.source_key)

        assert promoted.status == "succeeded"
        assert document_count == len(result.documents)
        assert embedding_count == len(result.documents)
        assert dimension == 3
        assert len(stored) == len(result.documents)
        assert all(item.embedding_dimension == 3 for item in stored)
        assert all(item.embedding_model == "test-embedding" for item in stored)
        assert all(item.source_fingerprint == snapshot.fingerprint for item in stored)
    finally:
        services.dispose()


def test_repeating_indexing_replaces_active_rows_without_duplicates(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    services, repository = _fresh_repository(postgres_fixture)
    try:
        snapshot = _snapshot(services)
        result = _documents(snapshot)
        first = _index_once(repository, result, "test-embedding")
        first_rows = repository.list_active_documents(result.source_key)
        second = _index_once(repository, result, "test-embedding")
        second_rows = repository.list_active_documents(result.source_key)

        assert first.status == "succeeded"
        assert second.status == "succeeded"
        assert len(second_rows) == len(first_rows)
        assert {row.document_key for row in second_rows} == {row.document_key for row in first_rows}
        assert repository.latest_run(result.source_key, status="succeeded") is not None
    finally:
        services.dispose()


def test_source_fingerprint_change_replaces_stale_documents(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    services, repository = _fresh_repository(postgres_fixture)
    try:
        original = _documents(_snapshot(services))
        _index_once(repository, original, "test-embedding")
        changed_snapshot = replace(_snapshot(services), fingerprint="sha256:changed")
        changed = _documents(changed_snapshot)
        _index_once(repository, changed, "test-embedding")

        rows = repository.list_active_documents(changed.source_key)
        assert rows
        assert {row.source_fingerprint for row in rows} == {"sha256:changed"}
    finally:
        services.dispose()


def test_failed_refresh_preserves_previous_active_index(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    services, repository = _fresh_repository(postgres_fixture)
    try:
        result = _documents(_snapshot(services))
        _index_once(repository, result, "test-embedding")
        before = repository.list_active_documents(result.source_key)
        failed_run = repository.start_run(
            source_key=result.source_key,
            source_fingerprint="sha256:failed",
            semantic_metadata_digest=result.semantic_metadata_digest,
            document_version=result.document_version,
            embedding_model="test-embedding",
            stale_reference_count=0,
        )
        failed = repository.fail_run(failed_run.run_id, "embedding_error")
        after = repository.list_active_documents(result.source_key)

        assert failed.status == "failed"
        assert failed.error_code == "embedding_error"
        assert after == before
    finally:
        services.dispose()


def test_index_repository_rejects_source_database_handle(
    postgres_fixture: PostgresIntegrationFixture,
) -> None:
    settings = fixture_settings(postgres_fixture)
    services = create_database_services(settings)
    try:
        assert services.source is not None
        with pytest.raises(DatabaseSeparationError):
            IndexRepository(cast(IndexDatabase, services.source))
    finally:
        services.dispose()


def _fresh_repository(
    postgres_fixture: PostgresIntegrationFixture,
) -> tuple[DatabaseServices, IndexRepository]:
    services = create_database_services(fixture_settings(postgres_fixture))
    assert services.index is not None
    with services.index.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS nl2sql_index CASCADE"))
    repository = IndexRepository(services.index)
    repository.initialize()
    return services, repository


def _snapshot(services: DatabaseServices) -> SourceSchemaSnapshot:
    assert services.source is not None
    return SourceIntrospector(services.source).introspect()


def _documents(snapshot: SourceSchemaSnapshot) -> SchemaDocumentBuildResult:
    catalog = load_semantic_metadata(Path("does-not-exist"))
    return SchemaDocumentBuilder().build(snapshot, catalog)


def _vectors(count: int) -> tuple[tuple[float, ...], ...]:
    return tuple((float(index), float(index + 1), float(index + 2)) for index in range(count))


def _index_once(
    repository: IndexRepository, result: SchemaDocumentBuildResult, model: str
) -> IndexRunRecord:
    run = repository.start_run(
        source_key=result.source_key,
        source_fingerprint=result.source_fingerprint,
        semantic_metadata_digest=result.semantic_metadata_digest,
        document_version=result.document_version,
        embedding_model=model,
        stale_reference_count=len(result.stale_semantic_references),
    )
    repository.stage_documents(run, result.documents, _vectors(len(result.documents)))
    return repository.promote_run(run)
