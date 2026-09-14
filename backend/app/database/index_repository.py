"""Transactional repository for the local schema-index database."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import and_, case, delete, func, insert, literal, or_, select, text, update

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
from app.models.retrieval import IndexSearchHit, RetrievedIndexDocument
from app.models.schema_index import (
    DocumentCategory,
    IndexDocument,
    IndexRunRecord,
    IndexRunStatus,
    StoredIndexDocument,
)

_MAX_RETRIEVAL_LIMIT = 256
_KEYWORD_TOKEN_LIMIT = 32


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

    def search_vector_documents(
        self,
        source_key: str,
        source_fingerprint: str,
        query_vector: Sequence[float],
        *,
        embedding_model: str,
        minimum_similarity: float,
        limit: int,
    ) -> tuple[IndexSearchHit, ...]:
        """Return bounded vector matches from the active local index."""

        _validate_retrieval_limit(limit)
        if not query_vector:
            raise IndexServiceError("The schema-index query vector must not be empty.")
        if not 0.0 <= minimum_similarity <= 1.0:
            raise IndexServiceError("The schema-index similarity threshold is invalid.")
        distance = schema_embeddings.c.embedding.cosine_distance(list(query_vector))
        similarity = (literal(1.0) - distance).label("vector_similarity")
        statement = (
            select(
                *_document_columns(),
                schema_embeddings.c.embedding_model,
                schema_embeddings.c.embedding_dimension,
                similarity,
            )
            .select_from(
                schema_documents.join(
                    schema_embeddings,
                    and_(
                        schema_documents.c.run_id == schema_embeddings.c.run_id,
                        schema_documents.c.document_key == schema_embeddings.c.document_key,
                    ),
                )
            )
            .where(
                and_(
                    schema_documents.c.source_key == source_key,
                    schema_documents.c.source_fingerprint == source_fingerprint,
                    schema_documents.c.active.is_(True),
                    schema_embeddings.c.embedding_model == embedding_model,
                    distance <= literal(1.0 - minimum_similarity),
                )
            )
            .order_by(
                similarity.desc(),
                schema_documents.c.category,
                schema_documents.c.qualified_identifier,
                schema_documents.c.document_key,
            )
            .limit(limit)
        )
        try:
            with self.database.connect() as connection:
                rows = connection.execute(statement).mappings()
                return tuple(
                    IndexSearchHit(
                        document=_retrieved_document(row),
                        signal="vector",
                        rank=rank,
                        raw_score=float(row["vector_similarity"]),
                        vector_similarity=float(row["vector_similarity"]),
                    )
                    for rank, row in enumerate(rows, start=1)
                )
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema vector search failed.") from exc

    def search_keyword_documents(
        self,
        source_key: str,
        source_fingerprint: str,
        question: str,
        *,
        limit: int,
    ) -> tuple[IndexSearchHit, ...]:
        """Return bounded PostgreSQL full-text and identifier matches."""

        _validate_retrieval_limit(limit)
        if not question.strip():
            return ()
        search_text = func.concat(
            schema_documents.c.content,
            literal(" "),
            schema_documents.c.qualified_identifier,
        )
        search_vector = func.to_tsvector("simple", search_text)
        search_query = func.plainto_tsquery("simple", question)
        terms = _keyword_terms(question)
        exact_match = _exact_identifier_match(terms)
        keyword_score = (
            func.ts_rank_cd(search_vector, search_query)
            + case((exact_match, literal(1.0)), else_=literal(0.0))
        ).label("keyword_score")
        statement = (
            select(*_document_columns(), keyword_score, exact_match.label("exact_identifier_match"))
            .where(
                and_(
                    schema_documents.c.source_key == source_key,
                    schema_documents.c.source_fingerprint == source_fingerprint,
                    schema_documents.c.active.is_(True),
                    or_(search_vector.op("@@")(search_query), exact_match),
                )
            )
            .order_by(
                keyword_score.desc(),
                schema_documents.c.category,
                schema_documents.c.qualified_identifier,
                schema_documents.c.document_key,
            )
            .limit(limit)
        )
        try:
            with self.database.connect() as connection:
                rows = connection.execute(statement).mappings()
                return tuple(
                    IndexSearchHit(
                        document=_retrieved_document(row),
                        signal="keyword",
                        rank=rank,
                        raw_score=float(row["keyword_score"]),
                        keyword_score=float(row["keyword_score"]),
                        exact_identifier_match=bool(row["exact_identifier_match"]),
                    )
                    for rank, row in enumerate(rows, start=1)
                )
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema keyword search failed.") from exc

    def list_active_relation_documents(
        self,
        source_key: str,
        source_fingerprint: str,
        relation_keys: Sequence[tuple[str, str]],
        *,
        category: str,
        limit: int,
    ) -> tuple[RetrievedIndexDocument, ...]:
        """Read bounded active documents for selected source relations."""

        _validate_retrieval_limit(limit)
        if not relation_keys:
            return ()
        statement = (
            _active_document_statement(source_key, source_fingerprint)
            .where(
                and_(
                    schema_documents.c.category == category,
                    _relation_filter(relation_keys),
                )
            )
            .order_by(schema_documents.c.qualified_identifier, schema_documents.c.document_key)
            .limit(limit)
        )
        return self._read_retrieved_documents(statement, "relation documents")

    def list_active_relationship_documents(
        self,
        source_key: str,
        source_fingerprint: str,
        relation_keys: Sequence[tuple[str, str]],
        *,
        direction: str,
        limit: int,
    ) -> tuple[RetrievedIndexDocument, ...]:
        """Read bounded foreign-key documents entering or leaving selected relations."""

        _validate_retrieval_limit(limit)
        if not relation_keys:
            return ()
        if direction == "outgoing":
            relation_filter = _relation_filter(relation_keys)
        elif direction == "incoming":
            relation_filter = _target_relation_filter(relation_keys)
        else:
            raise IndexServiceError("The relationship direction is invalid.")
        statement = (
            _active_document_statement(source_key, source_fingerprint)
            .where(and_(schema_documents.c.category == "relationship", relation_filter))
            .order_by(schema_documents.c.qualified_identifier, schema_documents.c.document_key)
            .limit(limit)
        )
        return self._read_retrieved_documents(statement, "relationship documents")

    def active_document_count(self, source_key: str, source_fingerprint: str) -> int:
        """Count active documents without loading the index into application memory."""

        statement = select(func.count()).select_from(
            _active_document_statement(source_key, source_fingerprint).subquery()
        )
        try:
            with self.database.connect() as connection:
                return int(connection.execute(statement).scalar_one())
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema index count could not be read.") from exc

    def active_embedding_count(
        self,
        source_key: str,
        source_fingerprint: str,
        *,
        embedding_model: str,
    ) -> int:
        """Count active documents with vectors from the expected embedding model."""

        statement = (
            select(func.count())
            .select_from(
                schema_documents.join(
                    schema_embeddings,
                    and_(
                        schema_documents.c.run_id == schema_embeddings.c.run_id,
                        schema_documents.c.document_key == schema_embeddings.c.document_key,
                    ),
                )
            )
            .where(
                and_(
                    schema_documents.c.source_key == source_key,
                    schema_documents.c.source_fingerprint == source_fingerprint,
                    schema_documents.c.active.is_(True),
                    schema_embeddings.c.embedding_model == embedding_model,
                )
            )
        )
        try:
            with self.database.connect() as connection:
                return int(connection.execute(statement).scalar_one())
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError("The local schema embedding count could not be read.") from exc

    def _read_retrieved_documents(
        self, statement: Any, description: str
    ) -> tuple[RetrievedIndexDocument, ...]:
        try:
            with self.database.connect() as connection:
                rows = connection.execute(statement).mappings()
                return tuple(_retrieved_document(row) for row in rows)
        except IndexServiceError:
            raise
        except Exception as exc:
            raise IndexServiceError(f"The local schema {description} could not be read.") from exc

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


def _document_columns() -> tuple[Any, ...]:
    return (
        schema_documents.c.document_key,
        schema_documents.c.category,
        schema_documents.c.source_key,
        schema_documents.c.schema_name,
        schema_documents.c.relation_name,
        schema_documents.c.column_name,
        schema_documents.c.target_schema_name,
        schema_documents.c.target_relation_name,
        schema_documents.c.target_column_names,
        schema_documents.c.qualified_identifier,
        schema_documents.c.content,
        schema_documents.c.metadata,
        schema_documents.c.source_fingerprint,
        schema_documents.c.semantic_metadata_digest,
        schema_documents.c.document_version,
        schema_documents.c.content_digest,
    )


def _active_document_statement(source_key: str, source_fingerprint: str) -> Any:
    return select(*_document_columns()).where(
        and_(
            schema_documents.c.source_key == source_key,
            schema_documents.c.source_fingerprint == source_fingerprint,
            schema_documents.c.active.is_(True),
        )
    )


def _relation_filter(relation_keys: Sequence[tuple[str, str]]) -> Any:
    return or_(
        *(
            and_(
                schema_documents.c.schema_name == schema_name,
                schema_documents.c.relation_name == relation_name,
            )
            for schema_name, relation_name in relation_keys
        )
    )


def _target_relation_filter(relation_keys: Sequence[tuple[str, str]]) -> Any:
    return or_(
        *(
            and_(
                schema_documents.c.target_schema_name == schema_name,
                schema_documents.c.target_relation_name == relation_name,
            )
            for schema_name, relation_name in relation_keys
        )
    )


def _retrieved_document(row: Any) -> RetrievedIndexDocument:
    return RetrievedIndexDocument(
        document_key=str(row["document_key"]),
        category=cast(Any, str(row["category"])),
        source_key=str(row["source_key"]),
        schema_name=str(row["schema_name"]),
        relation_name=cast(str | None, row["relation_name"]),
        column_name=cast(str | None, row["column_name"]),
        target_schema_name=cast(str | None, row["target_schema_name"]),
        target_relation_name=cast(str | None, row["target_relation_name"]),
        target_column_names=tuple(str(value) for value in (row["target_column_names"] or [])),
        qualified_identifier=str(row["qualified_identifier"]),
        content=str(row["content"]),
        metadata=cast(dict[str, Any], row["metadata"]),
        source_fingerprint=str(row["source_fingerprint"]),
        semantic_metadata_digest=str(row["semantic_metadata_digest"]),
        document_version=str(row["document_version"]),
        content_digest=str(row["content_digest"]),
    )


def _keyword_terms(question: str) -> tuple[str, ...]:
    terms: list[str] = []
    for raw_term in re.findall(r"[\w]+", question.casefold()):
        if raw_term and raw_term not in terms:
            terms.append(raw_term)
        if len(terms) == _KEYWORD_TOKEN_LIMIT:
            break
    return tuple(terms)


def _exact_identifier_match(terms: Sequence[str]) -> Any:
    if not terms:
        return literal(False)
    return or_(
        *(
            func.lower(column).in_(terms)
            for column in (
                schema_documents.c.schema_name,
                schema_documents.c.relation_name,
                schema_documents.c.column_name,
            )
        )
    )


def _validate_retrieval_limit(limit: int) -> None:
    if not 0 < limit <= _MAX_RETRIEVAL_LIMIT:
        raise IndexServiceError("The schema-index retrieval limit is outside the safe bound.")
