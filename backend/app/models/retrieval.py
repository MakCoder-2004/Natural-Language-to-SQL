"""Typed domain models for bounded hybrid schema retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from app.models.schema_index import DocumentCategory

RetrievalSignal = Literal["vector", "keyword"]
IndexReadinessStatus = Literal["ready"]


@dataclass(frozen=True, slots=True)
class RetrievedIndexDocument:
    """An active schema document read without its stored embedding vector."""

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
class IndexSearchHit:
    """One bounded result from a vector or non-vector search signal."""

    document: RetrievedIndexDocument
    signal: RetrievalSignal
    rank: int
    raw_score: float
    vector_similarity: float | None = None
    keyword_score: float | None = None
    exact_identifier_match: bool = False


@dataclass(frozen=True, slots=True)
class RankedSchemaDocument:
    """A document after hybrid signal fusion."""

    document: RetrievedIndexDocument
    fused_score: float
    vector_rank: int | None
    keyword_rank: int | None
    vector_similarity: float | None
    keyword_score: float | None
    exact_identifier_match: bool
    signals: tuple[RetrievalSignal, ...]


@dataclass(frozen=True, slots=True)
class RetrievalLimits:
    """Backend-owned bounds applied to one retrieval operation."""

    vector_candidate_limit: int
    keyword_candidate_limit: int
    max_selected_tables: int
    max_columns_per_table: int
    max_relationships: int
    max_relationship_hops: int
    max_expanded_tables: int
    max_context_documents: int
    max_context_characters: int
    min_vector_similarity: float
    vector_weight: float
    keyword_weight: float
    rrf_constant: int


@dataclass(frozen=True, slots=True)
class IndexReadiness:
    """Trusted active-index identity established before retrieval."""

    status: IndexReadinessStatus
    source_key: str
    source_fingerprint: str
    semantic_metadata_digest: str
    run_id: str
    embedding_model: str
    embedding_dimension: int
    document_count: int
    indexed_at: datetime | None


@dataclass(frozen=True, slots=True)
class RetrievedColumn:
    """One selected source column."""

    schema_name: str
    relation_name: str
    column_name: str
    data_type: str | None
    nullable: bool | None
    description: str | None
    roles: tuple[str, ...]
    score: float
    required: bool


@dataclass(frozen=True, slots=True)
class RetrievedTable:
    """One selected source relation."""

    schema_name: str
    relation_name: str
    relation_kind: str | None
    description: str | None
    score: float
    direct: bool
    evidence_document_keys: tuple[str, ...]
    columns: tuple[RetrievedColumn, ...]


@dataclass(frozen=True, slots=True)
class RetrievedRelationship:
    """One direction-preserving foreign-key relationship."""

    source_schema_name: str
    source_relation_name: str
    source_columns: tuple[str, ...]
    target_schema_name: str
    target_relation_name: str
    target_columns: tuple[str, ...]
    cardinality: str | None
    description: str | None
    score: float
    expanded: bool
    document_key: str


@dataclass(frozen=True, slots=True)
class RetrievalDiagnostics:
    """Safe measurements and counts from one retrieval operation."""

    vector_candidate_count: int
    keyword_candidate_count: int
    fused_candidate_count: int
    selected_table_count: int
    selected_column_count: int
    relationship_count: int
    expanded_table_count: int
    stage_latency_ms: dict[str, float]
    limits: RetrievalLimits


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Compact schema context and its supporting structured data."""

    documents: tuple[Any, ...]
    tables: tuple[RetrievedTable, ...]
    columns: tuple[RetrievedColumn, ...]
    relationships: tuple[RetrievedRelationship, ...]
    context_text: str
    index_fingerprint: str
    diagnostics: RetrievalDiagnostics
