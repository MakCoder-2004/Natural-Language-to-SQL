"""Local-only PostgreSQL and pgvector schema for the schema index."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

INDEX_SCHEMA_NAME = "nl2sql_index"

index_metadata = MetaData()

index_runs = Table(
    "index_runs",
    index_metadata,
    Column("run_id", String(64), primary_key=True),
    Column("source_key", Text, nullable=False),
    Column("source_fingerprint", String(72), nullable=False),
    Column("semantic_metadata_digest", String(72), nullable=False),
    Column("document_version", String(128), nullable=False),
    Column("embedding_model", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("embedding_dimension", Integer),
    Column("document_count", Integer, nullable=False, default=0),
    Column("embedding_count", Integer, nullable=False, default=0),
    Column("stale_reference_count", Integer, nullable=False, default=0),
    Column("error_code", String(128)),
    schema=INDEX_SCHEMA_NAME,
)

schema_metadata = Table(
    "schema_metadata",
    index_metadata,
    Column(
        "run_id",
        String(64),
        ForeignKey(f"{INDEX_SCHEMA_NAME}.index_runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("document_key", String(128), primary_key=True),
    Column("category", String(32), nullable=False),
    Column("source_key", Text, nullable=False),
    Column("schema_name", Text, nullable=False),
    Column("relation_name", Text),
    Column("column_name", Text),
    Column("qualified_identifier", Text, nullable=False),
    Column("technical_metadata", JSON, nullable=False),
    Column("semantic_metadata_digest", String(72), nullable=False),
    Column("source_fingerprint", String(72), nullable=False),
    Column("document_version", String(128), nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
    schema=INDEX_SCHEMA_NAME,
)

schema_documents = Table(
    "schema_documents",
    index_metadata,
    Column(
        "run_id",
        String(64),
        ForeignKey(f"{INDEX_SCHEMA_NAME}.index_runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("document_key", String(128), primary_key=True),
    Column("category", String(32), nullable=False),
    Column("source_key", Text, nullable=False),
    Column("schema_name", Text, nullable=False),
    Column("relation_name", Text),
    Column("column_name", Text),
    Column("target_schema_name", Text),
    Column("target_relation_name", Text),
    Column("target_column_names", JSON, nullable=False),
    Column("qualified_identifier", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("metadata", JSON, nullable=False),
    Column("source_fingerprint", String(72), nullable=False),
    Column("semantic_metadata_digest", String(72), nullable=False),
    Column("document_version", String(128), nullable=False),
    Column("content_digest", String(72), nullable=False),
    Column("active", Boolean, nullable=False, default=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
    schema=INDEX_SCHEMA_NAME,
)

schema_embeddings = Table(
    "schema_embeddings",
    index_metadata,
    Column("run_id", String(64), primary_key=True),
    Column("document_key", String(128), primary_key=True),
    Column("embedding", Vector(), nullable=False),
    Column("embedding_model", Text, nullable=False),
    Column("embedding_dimension", Integer, nullable=False),
    Column("content_digest", String(72), nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["run_id", "document_key"],
        [
            f"{INDEX_SCHEMA_NAME}.schema_documents.run_id",
            f"{INDEX_SCHEMA_NAME}.schema_documents.document_key",
        ],
        ondelete="CASCADE",
    ),
    schema=INDEX_SCHEMA_NAME,
)

Index(
    "uq_active_schema_document_key",
    schema_documents.c.source_key,
    schema_documents.c.document_key,
    unique=True,
    postgresql_where=schema_documents.c.active.is_(True),
)
Index(
    "ix_active_schema_documents_source_category",
    schema_documents.c.source_key,
    schema_documents.c.category,
    postgresql_where=schema_documents.c.active.is_(True),
)
