"""Domain models for schema documents and local index runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

DocumentCategory = Literal["table", "column", "relationship", "semantic_concept"]


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
