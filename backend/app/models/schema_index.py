"""Domain models for schema documents and local index runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

DocumentCategory = Literal["table", "column", "relationship", "semantic_concept"]
IndexRunStatus = Literal["running", "succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class IndexDocument:
    """One deterministic, embedding-ready schema document."""

    document_key: str
    category: DocumentCategory
    source_key: str
    schema_name: str
    relation_name: str | None
    column_name: str | None
    target_schema_name: str | None
    target_relation_name: str | None
    target_column_names: tuple[str, ...]
    qualified_identifier: str
    content: str
    metadata: dict[str, Any]
    source_fingerprint: str
    semantic_metadata_digest: str
    document_version: str
    content_digest: str


@dataclass(frozen=True, slots=True)
class SchemaDocumentBuildResult:
    """Documents and diagnostics produced from one source snapshot."""

    documents: tuple[IndexDocument, ...]
    stale_semantic_references: tuple[str, ...]
    source_key: str
    source_fingerprint: str
    semantic_metadata_digest: str
    document_version: str


@dataclass(frozen=True, slots=True)
class IndexRunRecord:
    """Safe metadata describing one local index build attempt."""

    run_id: str
    source_key: str
    source_fingerprint: str
    semantic_metadata_digest: str
    document_version: str
    embedding_model: str
    status: IndexRunStatus
    started_at: datetime
    finished_at: datetime | None
    embedding_dimension: int | None
    document_count: int
    embedding_count: int
    stale_reference_count: int
    error_code: str | None


@dataclass(frozen=True, slots=True)
class StoredIndexDocument:
    """An active indexed document and its stored vector."""

    document_key: str
    category: DocumentCategory
    source_key: str
    qualified_identifier: str
    content: str
    metadata: dict[str, Any]
    embedding: tuple[float, ...]
    embedding_model: str
    embedding_dimension: int
    source_fingerprint: str
    semantic_metadata_digest: str
    document_version: str
    content_digest: str
