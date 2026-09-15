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


class IndexReadinessError(IndexServiceError):
    """Raised when the local schema index cannot safely serve retrieval."""

    error_code = "index_not_ready"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class NoRelevantSchemaError(IndexServiceError):
    """Raised when retrieval cannot establish credible schema context."""

    error_code = "no_relevant_schema"


class ModelServiceError(RuntimeError):
    """Raised when a configured model cannot produce a valid response."""

    error_code = "model_error"


class ModelTimeoutError(ModelServiceError):
    """Raised when a model does not respond within its configured deadline."""

    error_code = "model_timeout"


class ModelUnavailableError(ModelServiceError):
    """Raised when the configured model provider cannot serve a request."""

    error_code = "model_unavailable"


class ModelOutputError(ModelServiceError):
    """Raised when a provider response cannot satisfy a structured contract."""

    error_code = "model_output_error"


def translate_model_exception(message: str, error: Exception) -> ModelServiceError:
    """Classify common provider failures without returning provider details."""

    name = type(error).__name__.lower()
    status_code = getattr(error, "status_code", None)
    if "timeout" in name or isinstance(error, TimeoutError):
        return ModelTimeoutError(message)
    if status_code in {401, 403, 404, 408, 409, 429} or (
        isinstance(status_code, int) and status_code >= 500
    ):
        return ModelUnavailableError(message)
    if "connection" in name or "ratelimit" in name or "serviceunavailable" in name:
        return ModelUnavailableError(message)
    return ModelServiceError(message)


class QueryValidationError(RuntimeError):
    """Raised when generated SQL cannot be authorized."""

    error_code = "query_validation_error"


class QueryExecutionError(DatabaseServiceError):
    """Raised when an authorized source query cannot complete safely."""

    error_code = "query_execution_error"


class QueryTimeoutError(QueryExecutionError):
    """Raised when PostgreSQL terminates a query at the configured timeout."""

    error_code = "query_timeout"
