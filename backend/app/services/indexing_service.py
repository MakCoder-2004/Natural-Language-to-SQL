"""Repeatable source-to-pgvector schema indexing orchestration."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.config import Settings
from app.database.errors import DatabaseServiceError, IndexServiceError
from app.database.index_repository import IndexRepository
from app.database.services import DatabaseServices
from app.database.source_introspection import SourceIntrospector
from app.models.schema_index import IndexDocument, IndexRunRecord
from app.retrieval.embeddings import EmbeddingProvider, create_embedding_provider
from app.retrieval.schema_documents import SchemaDocumentBuilder
from app.retrieval.semantic_metadata import load_semantic_metadata

logger = logging.getLogger(__name__)


class IndexingService:
    """Coordinate source introspection, document construction, and local indexing."""

    def __init__(
        self,
        settings: Settings,
        database_services: DatabaseServices,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        if database_services.source is None or database_services.index is None:
            raise IndexServiceError("Source and index databases are required for indexing.")
        self.settings = settings
        self.source = database_services.source
        self.repository = IndexRepository(database_services.index)
        self.embedding_provider = embedding_provider

    def run(self) -> IndexRunRecord:
        """Build and atomically promote one complete schema index run."""

        run: IndexRunRecord | None = None
        try:
            self.repository.initialize()
            snapshot = SourceIntrospector(self.source).introspect()
            catalog = load_semantic_metadata(self.settings.semantic_metadata_path)
            build_result = SchemaDocumentBuilder(
                strict_semantic_metadata=self.settings.strict_semantic_metadata
            ).build(snapshot, catalog)
            provider = self.embedding_provider or create_embedding_provider(self.settings)
            with self.repository.run_lock(build_result.source_key):
                run = self.repository.start_run(
                    source_key=build_result.source_key,
                    source_fingerprint=build_result.source_fingerprint,
                    semantic_metadata_digest=build_result.semantic_metadata_digest,
                    document_version=build_result.document_version,
                    embedding_model=provider.model_id,
                    stale_reference_count=len(build_result.stale_semantic_references),
                )
                embeddings = self._embed_documents(provider, build_result.documents)
                self.repository.stage_documents(run, build_result.documents, embeddings)
                promoted = self.repository.promote_run(run)
            logger.info(
                "schema_index_run_succeeded run_id=%s source_key=%s "
                "document_count=%d embedding_count=%d",
                promoted.run_id,
                promoted.source_key,
                promoted.document_count,
                promoted.embedding_count,
            )
            return promoted
        except Exception as exc:
            error_code = _error_code(exc)
            if run is not None:
                try:
                    failed = self.repository.fail_run(run.run_id, error_code)
                    logger.error(
                        "schema_index_run_failed run_id=%s error_code=%s",
                        failed.run_id,
                        error_code,
                    )
                except Exception:
                    logger.error(
                        "schema_index_run_cleanup_failed run_id=%s error_code=%s",
                        run.run_id,
                        error_code,
                    )
            else:
                logger.error("schema_index_failed_before_run error_code=%s", error_code)
            if isinstance(exc, (DatabaseServiceError, IndexServiceError)):
                raise
            raise IndexServiceError("Schema indexing failed.") from exc

    def _embed_documents(
        self, provider: EmbeddingProvider, documents: Sequence[IndexDocument]
    ) -> tuple[tuple[float, ...], ...]:
        vectors: list[tuple[float, ...]] = []
        batch_size = self.settings.embedding_batch_size
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            vectors.extend(provider.embed_documents([document.content for document in batch]))
        if len(vectors) != len(documents):
            raise IndexServiceError("The embedding provider returned an unexpected vector count.")
        return tuple(vectors)


def _error_code(error: Exception) -> str:
    value = getattr(error, "error_code", None)
    return value if isinstance(value, str) else "indexing_failed"
