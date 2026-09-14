"""Transactional repository for the local schema-index database."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import and_, delete, insert, select, text, update

from app.database.errors import DatabaseSeparationError, IndexServiceError
from app.database.index_connection import IndexDatabase
from app.database.index_schema import (
    INDEX_SCHEMA_NAME,
    index_metadata,
    index_runs,
    schema_documents,
    schema_embeddings,
    schema_metadata,
)
from app.models.schema_index import (
    DocumentCategory,
    IndexDocument,
    IndexRunRecord,
    IndexRunStatus,
    StoredIndexDocument,
)


class IndexRepository:
    """Store only schema metadata, rendered documents, and embeddings locally."""

    def __init__(self, database: IndexDatabase) -> None:
        if not isinstance(database, IndexDatabase):
            raise DatabaseSeparationError("The schema index requires an index database handle.")
        self.database = database

    def initialize(self) -> None:
        """Create the local extension, namespace, and tables idempotently."""

        try:
            with self.database.begin() as connection:
                connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {INDEX_SCHEMA_NAME}"))
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                index_metadata.create_all(connection)
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index could not be initialized.") from exc

    @contextmanager
    def run_lock(self, source_key: str) -> Iterator[None]:
        """Serialize indexing runs for one source namespace."""

        try:
            with self.database.connect() as connection:
                connection.execute(
                    text("SELECT pg_advisory_lock(hashtextextended(:source_key, :lock_seed))"),
                    {"source_key": source_key, "lock_seed": 0},
                )
                try:
                    yield
                finally:
                    connection.execute(
                        text(
                            "SELECT pg_advisory_unlock(hashtextextended(:source_key, :lock_seed))"
                        ),
                        {"source_key": source_key, "lock_seed": 0},
                    )
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index lock could not be acquired.") from exc

    def start_run(
        self,
        *,
        source_key: str,
        source_fingerprint: str,
        semantic_metadata_digest: str,
        document_version: str,
        embedding_model: str,
        stale_reference_count: int,
    ) -> IndexRunRecord:
        """Create a staged indexing run."""

        run = IndexRunRecord(
            run_id=uuid.uuid4().hex,
            source_key=source_key,
            source_fingerprint=source_fingerprint,
            semantic_metadata_digest=semantic_metadata_digest,
            document_version=document_version,
            embedding_model=embedding_model,
            status="running",
            started_at=datetime.now(UTC),
            finished_at=None,
            embedding_dimension=None,
            document_count=0,
            embedding_count=0,
            stale_reference_count=stale_reference_count,
            error_code=None,
        )
        try:
            with self.database.begin() as connection:
                connection.execute(insert(index_runs).values(_run_values(run)))
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index run could not be started.") from exc
        return run

    def stage_documents(
        self,
        run: IndexRunRecord,
        documents: Sequence[IndexDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> tuple[int, int, int]:
        """Write a complete run's metadata, documents, and vectors as staged rows."""

        if len(documents) != len(embeddings):
            raise IndexServiceError("Document and embedding counts do not match.")
        dimensions = {len(vector) for vector in embeddings}
        if len(dimensions) > 1 or (dimensions and next(iter(dimensions)) == 0):
            raise IndexServiceError("Index embeddings must have one non-zero dimension.")
        embedding_dimension = next(iter(dimensions), None)
        now = datetime.now(UTC)
        metadata_rows = [
            {
                "run_id": run.run_id,
                "document_key": document.document_key,
                "category": document.category,
                "source_key": document.source_key,
                "schema_name": document.schema_name,
                "relation_name": document.relation_name,
                "column_name": document.column_name,
                "qualified_identifier": document.qualified_identifier,
                "technical_metadata": document.metadata,
                "semantic_metadata_digest": document.semantic_metadata_digest,
                "source_fingerprint": document.source_fingerprint,
                "document_version": document.document_version,
                "indexed_at": now,
            }
            for document in documents
        ]
        document_rows = [
            {
                "run_id": run.run_id,
                "document_key": document.document_key,
                "category": document.category,
                "source_key": document.source_key,
                "schema_name": document.schema_name,
                "relation_name": document.relation_name,
                "column_name": document.column_name,
                "target_schema_name": document.target_schema_name,
                "target_relation_name": document.target_relation_name,
                "target_column_names": list(document.target_column_names),
                "qualified_identifier": document.qualified_identifier,
                "content": document.content,
                "metadata": document.metadata,
                "source_fingerprint": document.source_fingerprint,
                "semantic_metadata_digest": document.semantic_metadata_digest,
                "document_version": document.document_version,
                "content_digest": document.content_digest,
                "active": False,
                "indexed_at": now,
            }
            for document in documents
        ]
        embedding_rows = [
            {
                "run_id": run.run_id,
                "document_key": document.document_key,
                "embedding": list(vector),
                "embedding_model": run.embedding_model,
                "embedding_dimension": len(vector),
                "content_digest": document.content_digest,
                "indexed_at": now,
            }
            for document, vector in zip(documents, embeddings, strict=True)
        ]
        try:
            with self.database.begin() as connection:
                if metadata_rows:
                    connection.execute(insert(schema_metadata), metadata_rows)
                    connection.execute(insert(schema_documents), document_rows)
                    connection.execute(insert(schema_embeddings), embedding_rows)
                connection.execute(
                    update(index_runs)
                    .where(index_runs.c.run_id == run.run_id)
                    .values(
                        embedding_dimension=embedding_dimension,
                        document_count=len(documents),
                        embedding_count=len(embeddings),
                    )
                )
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError(
                "The local schema index documents could not be staged."
            ) from exc
        return len(documents), len(embeddings), embedding_dimension or 0

    def promote_run(self, run: IndexRunRecord) -> IndexRunRecord:
        """Atomically replace the active index with a completed staged run."""

        finished_at = datetime.now(UTC)
        try:
            with self.database.begin() as connection:
                current = (
                    connection.execute(select(index_runs).where(index_runs.c.run_id == run.run_id))
                    .mappings()
                    .one()
                )
                source_key = str(current["source_key"])
                connection.execute(
                    update(schema_documents)
                    .where(
                        and_(
                            schema_documents.c.source_key == source_key,
                            schema_documents.c.active.is_(True),
                        )
                    )
                    .values(active=False)
                )
                connection.execute(
                    update(schema_documents)
                    .where(schema_documents.c.run_id == run.run_id)
                    .values(active=True)
                )
                connection.execute(
                    delete(schema_metadata).where(
                        and_(
                            schema_metadata.c.source_key == source_key,
                            schema_metadata.c.run_id != run.run_id,
                        )
                    )
                )
                connection.execute(
                    delete(schema_documents).where(
                        and_(
                            schema_documents.c.source_key == source_key,
                            schema_documents.c.run_id != run.run_id,
                        )
                    )
                )
                connection.execute(
                    update(index_runs)
                    .where(index_runs.c.run_id == run.run_id)
                    .values(status="succeeded", finished_at=finished_at)
                )
                promoted = (
                    connection.execute(select(index_runs).where(index_runs.c.run_id == run.run_id))
                    .mappings()
                    .one()
                )
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index run could not be promoted.") from exc
        return _run_record(promoted)

    def fail_run(self, run_id: str, error_code: str) -> IndexRunRecord:
        """Mark a run failed and remove its staged rows without touching active data."""

        safe_error_code = error_code[:128]
        finished_at = datetime.now(UTC)
        try:
            with self.database.begin() as connection:
                connection.execute(
                    delete(schema_metadata).where(schema_metadata.c.run_id == run_id)
                )
                connection.execute(
                    delete(schema_documents).where(schema_documents.c.run_id == run_id)
                )
                connection.execute(
                    update(index_runs)
                    .where(index_runs.c.run_id == run_id)
                    .values(status="failed", finished_at=finished_at, error_code=safe_error_code)
                )
                failed = (
                    connection.execute(select(index_runs).where(index_runs.c.run_id == run_id))
                    .mappings()
                    .one()
                )
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError(
                "The local schema index run could not be marked failed."
            ) from exc
        return _run_record(failed)

    def list_active_documents(self, source_key: str) -> tuple[StoredIndexDocument, ...]:
        """Read active documents and vectors from the local index only."""

        try:
            with self.database.connect() as connection:
                rows = connection.execute(
                    select(
                        schema_documents,
                        schema_embeddings.c.embedding,
                        schema_embeddings.c.embedding_model,
                        schema_embeddings.c.embedding_dimension,
                    )
                    .join(
                        schema_embeddings,
                        and_(
                            schema_documents.c.run_id == schema_embeddings.c.run_id,
                            schema_documents.c.document_key == schema_embeddings.c.document_key,
                        ),
                    )
                    .where(
                        and_(
                            schema_documents.c.source_key == source_key,
                            schema_documents.c.active.is_(True),
                        )
                    )
                    .order_by(schema_documents.c.category, schema_documents.c.qualified_identifier)
                ).mappings()
                return tuple(_stored_document(row) for row in rows)
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index could not be read.") from exc

    def latest_run(self, source_key: str, *, status: str | None = None) -> IndexRunRecord | None:
        """Return the latest run for a source namespace."""

        try:
            with self.database.connect() as connection:
                statement = select(index_runs).where(index_runs.c.source_key == source_key)
                if status is not None:
                    statement = statement.where(index_runs.c.status == status)
                row = (
                    connection.execute(statement.order_by(index_runs.c.started_at.desc()).limit(1))
                    .mappings()
                    .one_or_none()
                )
                return _run_record(row) if row is not None else None
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index status could not be read.") from exc


def _run_values(run: IndexRunRecord) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "source_key": run.source_key,
        "source_fingerprint": run.source_fingerprint,
        "semantic_metadata_digest": run.semantic_metadata_digest,
        "document_version": run.document_version,
        "embedding_model": run.embedding_model,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "embedding_dimension": run.embedding_dimension,
        "document_count": run.document_count,
        "embedding_count": run.embedding_count,
        "stale_reference_count": run.stale_reference_count,
        "error_code": run.error_code,
    }


def _run_record(row: Any) -> IndexRunRecord:
    return IndexRunRecord(
        run_id=str(row["run_id"]),
        source_key=str(row["source_key"]),
        source_fingerprint=str(row["source_fingerprint"]),
        semantic_metadata_digest=str(row["semantic_metadata_digest"]),
        document_version=str(row["document_version"]),
        embedding_model=str(row["embedding_model"]),
        status=cast(IndexRunStatus, str(row["status"])),
        started_at=cast(datetime, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
        embedding_dimension=cast(int | None, row["embedding_dimension"]),
        document_count=int(row["document_count"]),
        embedding_count=int(row["embedding_count"]),
        stale_reference_count=int(row["stale_reference_count"]),
        error_code=cast(str | None, row["error_code"]),
    )


def _stored_document(row: Any) -> StoredIndexDocument:
    embedding = row["embedding"]
    if not isinstance(embedding, (list, tuple)):
        raise IndexServiceError("The local schema index returned an invalid vector.")
    return StoredIndexDocument(
        document_key=str(row["document_key"]),
        category=cast(DocumentCategory, str(row["category"])),
        source_key=str(row["source_key"]),
        qualified_identifier=str(row["qualified_identifier"]),
        content=str(row["content"]),
        metadata=cast(dict[str, Any], row["metadata"]),
        embedding=tuple(float(value) for value in embedding),
        embedding_model=str(row["embedding_model"]),
        embedding_dimension=int(row["embedding_dimension"]),
        source_fingerprint=str(row["source_fingerprint"]),
        semantic_metadata_digest=str(row["semantic_metadata_digest"]),
        document_version=str(row["document_version"]),
        content_digest=str(row["content_digest"]),
    )
