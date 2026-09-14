from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from app.config import Settings
from app.database.errors import EmbeddingServiceError, IndexReadinessError
from app.database.index_repository import IndexRepository
from app.database.services import create_database_services
from app.services.health import build_health_response
from app.services.indexing_service import IndexingService
from app.services.retrieval import HybridSchemaRetrievalService

from tests.fixtures.postgres import PostgresIntegrationFixture, fixture_settings

pytestmark = pytest.mark.integration


class FakeEmbeddingProvider:
    model_id = "test-embedding"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        batch = list(texts)
        self.batches.append(batch)
        return tuple((float(len(text)), 1.0, 2.0) for text in batch)

    def embed_query(self, text: str) -> tuple[float, ...]:
        return (float(len(text)), 1.0, 2.0)


class FailingEmbeddingProvider:
    model_id = "test-embedding"

    def embed_documents(self, _texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        raise EmbeddingServiceError("test embedding failure")

    def embed_query(self, _text: str) -> tuple[float, ...]:
        raise EmbeddingServiceError("test embedding failure")


def test_indexing_service_runs_source_to_local_index_in_batches(
    postgres_fixture: PostgresIntegrationFixture,
    tmp_path: Path,
) -> None:
    settings = _test_settings(postgres_fixture, tmp_path, embedding_batch_size=2)
    services = create_database_services(settings)
    provider = FakeEmbeddingProvider()
    try:
        run = IndexingService(settings, services, embedding_provider=provider).run()

        assert run.status == "succeeded"
        assert run.document_count > 0
        assert run.embedding_count == run.document_count
        assert len(provider.batches) > 1
        assert all(len(batch) <= 2 for batch in provider.batches)
        assert services.index is not None
        stored = IndexRepository(services.index).list_active_documents(run.source_key)
        assert len(stored) == run.document_count
    finally:
        services.dispose()


def test_failed_embedding_run_preserves_previous_active_index(
    postgres_fixture: PostgresIntegrationFixture,
    tmp_path: Path,
) -> None:
    settings = _test_settings(postgres_fixture, tmp_path)
    services = create_database_services(settings)
    try:
        successful = IndexingService(
            settings, services, embedding_provider=FakeEmbeddingProvider()
        ).run()
        assert successful.status == "succeeded"
        assert services.index is not None
        repository = IndexRepository(services.index)
        before = repository.list_active_documents(successful.source_key)

        with pytest.raises(EmbeddingServiceError):
            IndexingService(settings, services, embedding_provider=FailingEmbeddingProvider()).run()

        after = repository.list_active_documents(successful.source_key)
        latest = repository.latest_run(successful.source_key)
        assert after == before
        assert latest is not None
        assert latest.status == "failed"
        assert latest.error_code == "embedding_error"
    finally:
        services.dispose()


def test_health_reports_ready_and_stale_index_states(
    postgres_fixture: PostgresIntegrationFixture,
    tmp_path: Path,
) -> None:
    settings = _test_settings(postgres_fixture, tmp_path)
    services = create_database_services(settings)
    try:
        successful = IndexingService(
            settings, services, embedding_provider=FakeEmbeddingProvider()
        ).run()
        ready = build_health_response(settings, services)

        metadata_file = tmp_path / "semantic.yaml"
        metadata_file.write_text(
            "metadata_version: 1\nschemas:\n  - name: analytics\n    description: changed\n",
            encoding="utf-8",
        )
        stale_settings = settings.model_copy(update={"semantic_metadata_path": str(metadata_file)})
        stale = build_health_response(stale_settings, services)

        assert successful.status == "succeeded"
        assert ready.status == "ready"
        assert ready.schema_index.status == "ready"
        assert ready.schema_index.document_count == successful.document_count
        assert stale.status == "degraded"
        assert stale.schema_index.status == "stale"
        assert stale.schema_index.freshness_checked is True
    finally:
        services.dispose()


def test_hybrid_schema_retrieval_returns_bounded_context_and_relationships(
    postgres_fixture: PostgresIntegrationFixture,
    tmp_path: Path,
) -> None:
    settings = _test_settings(
        postgres_fixture,
        tmp_path,
        retrieval_max_selected_tables=1,
        retrieval_max_columns_per_table=2,
        retrieval_max_relationships=1,
        retrieval_max_expanded_tables=1,
    )
    services = create_database_services(settings)
    try:
        provider = FakeEmbeddingProvider()
        run = IndexingService(settings, services, embedding_provider=provider).run()
        result = HybridSchemaRetrievalService(
            settings,
            services,
            embedding_provider=provider,
        ).retrieve("events")

        assert run.status == "succeeded"
        assert result.index_fingerprint == run.source_fingerprint
        assert len(result.tables) <= 2
        assert len(result.tables) < 4
        assert len(result.columns) <= 4
        assert len(result.relationships) <= 1
        assert len(result.context_text) <= settings.retrieval_max_context_characters
        assert result.diagnostics.vector_candidate_count > 0
        assert result.diagnostics.keyword_candidate_count > 0
        assert result.diagnostics.stage_latency_ms["total"] >= 0
        assert result.relationships
        assert all(relationship.source_columns for relationship in result.relationships)
        assert all(relationship.target_columns for relationship in result.relationships)
        assert '"internal"' not in result.context_text

        stale_metadata = tmp_path / "changed-metadata.yaml"
        stale_metadata.write_text(
            "metadata_version: 1\nschemas:\n  - name: analytics\n    description: changed\n",
            encoding="utf-8",
        )
        stale_settings = settings.model_copy(update={"semantic_metadata_path": str(stale_metadata)})
        with pytest.raises(IndexReadinessError) as raised:
            HybridSchemaRetrievalService(
                stale_settings,
                services,
                embedding_provider=provider,
            ).retrieve("events")
        assert raised.value.reason == "index_stale"
    finally:
        services.dispose()


def _test_settings(
    fixture: PostgresIntegrationFixture,
    tmp_path: Path,
    *,
    embedding_batch_size: int = 64,
    retrieval_max_selected_tables: int = 8,
    retrieval_max_columns_per_table: int = 12,
    retrieval_max_relationships: int = 8,
    retrieval_max_expanded_tables: int = 4,
) -> Settings:
    return fixture_settings(fixture).model_copy(
        update={
            "semantic_metadata_path": str(tmp_path / "missing-metadata"),
            "embedding_batch_size": embedding_batch_size,
            "retrieval_max_selected_tables": retrieval_max_selected_tables,
            "retrieval_max_columns_per_table": retrieval_max_columns_per_table,
            "retrieval_max_relationships": retrieval_max_relationships,
            "retrieval_max_expanded_tables": retrieval_max_expanded_tables,
        }
    )
