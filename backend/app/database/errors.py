"""Safe domain errors for database connection and metadata operations."""

from __future__ import annotations


class DatabaseServiceError(RuntimeError):
    """Base error whose message is safe to expose at an application boundary."""

    error_code = "database_error"


class DatabaseUnavailableError(DatabaseServiceError):
    """Raised when a database cannot be reached within configured limits."""

    error_code = "database_unavailable"


class DatabasePermissionError(DatabaseServiceError):
    """Raised when the configured database role lacks required access."""

    error_code = "database_permission_denied"


class DatabaseSeparationError(DatabaseServiceError):
    """Raised when a database handle is used for the wrong boundary."""

    error_code = "database_separation_error"


class SourceSchemaNotFoundError(DatabaseServiceError):
    """Raised when a configured source schema does not exist."""

    error_code = "source_schema_not_found"


class SourceIntrospectionError(DatabaseServiceError):
    """Raised when source metadata cannot be collected safely."""

    error_code = "source_introspection_error"


class IndexServiceError(RuntimeError):
    """Base error for local schema-index operations."""

    error_code = "index_error"


class SemanticMetadataError(IndexServiceError):
    """Raised when version-controlled semantic metadata is invalid."""

    error_code = "semantic_metadata_error"


class EmbeddingServiceError(IndexServiceError):
    """Raised when an embedding provider cannot produce valid vectors."""

    error_code = "embedding_error"
