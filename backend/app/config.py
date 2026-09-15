"""Typed application settings and safe startup configuration validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.models.model_roles import ModelRole

DEFAULT_SOURCE_SCHEMA_SCOPE: Final[str] = "public"
MAX_ALLOWED_CORRECTION_RETRIES: Final[int] = 2
DEFAULT_MAX_REGENERATION_COUNT: Final[int] = 3
SYSTEM_SCHEMAS: Final[frozenset[str]] = frozenset({"information_schema", "pg_catalog", "pg_toast"})
DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_SOURCE_POOL_SIZE: Final[int] = 5
DEFAULT_SOURCE_MAX_OVERFLOW: Final[int] = 10
DEFAULT_SOURCE_POOL_TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_SOURCE_POOL_RECYCLE_SECONDS: Final[int] = 1800
DEFAULT_INDEX_POOL_SIZE: Final[int] = 5
DEFAULT_INDEX_MAX_OVERFLOW: Final[int] = 10
DEFAULT_INDEX_POOL_TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_INDEX_POOL_RECYCLE_SECONDS: Final[int] = 1800
DEFAULT_EMBEDDING_BATCH_SIZE: Final[int] = 64
DEFAULT_EMBEDDING_REQUEST_TIMEOUT_SECONDS: Final[int] = 300
DEFAULT_RETRIEVAL_VECTOR_CANDIDATE_LIMIT: Final[int] = 16
DEFAULT_RETRIEVAL_KEYWORD_CANDIDATE_LIMIT: Final[int] = 16
DEFAULT_RETRIEVAL_MAX_SELECTED_TABLES: Final[int] = 8
DEFAULT_RETRIEVAL_MAX_COLUMNS_PER_TABLE: Final[int] = 12
DEFAULT_RETRIEVAL_MAX_RELATIONSHIPS: Final[int] = 8
DEFAULT_RETRIEVAL_MAX_RELATIONSHIP_HOPS: Final[int] = 1
DEFAULT_RETRIEVAL_MAX_EXPANDED_TABLES: Final[int] = 4
DEFAULT_RETRIEVAL_MAX_CONTEXT_DOCUMENTS: Final[int] = 64
DEFAULT_RETRIEVAL_MAX_CONTEXT_CHARACTERS: Final[int] = 12_000
DEFAULT_RETRIEVAL_MIN_VECTOR_SIMILARITY: Final[float] = 0.20
DEFAULT_RETRIEVAL_VECTOR_WEIGHT: Final[float] = 0.60
DEFAULT_RETRIEVAL_KEYWORD_WEIGHT: Final[float] = 0.40
DEFAULT_RETRIEVAL_RRF_CONSTANT: Final[int] = 60
DEFAULT_MAX_QUESTION_LENGTH: Final[int] = 2_000
DEFAULT_MODEL_REQUEST_TIMEOUT_SECONDS: Final[int] = 180


@dataclass(frozen=True, slots=True)
class ConfigurationIssue:
    """A safe, user-facing description of one configuration problem."""

    field: str
    code: str
    message: str


class ConfigurationError(ValueError):
    """Raised when configuration is not sufficient for an operation."""

    def __init__(self, issues: tuple[ConfigurationIssue, ...]) -> None:
        self.issues = issues
        message = "; ".join(issue.message for issue in issues)
        super().__init__(f"Application configuration is invalid: {message}")


class Settings(BaseSettings):
    """Backend-owned settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    source_database_url: SecretStr | None = None
    index_database_url: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str | None = None
    openrouter_site_name: str | None = None
    model_provider: Literal["openrouter", "ollama"] = "openrouter"
    ollama_base_url: str = "http://localhost:11434"
    embedding_provider: Literal["openrouter", "ollama"] = "openrouter"

    question_model: str | None = None
    sql_model: str | None = None
    sql_correction_model: str | None = None
    answer_model: str | None = None
    embedding_model: str | None = None

    source_schema_scope: str = DEFAULT_SOURCE_SCHEMA_SCOPE
    semantic_metadata_path: str = "../schema_index/metadata"
    database_connect_timeout_seconds: int = DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS
    source_pool_size: int = DEFAULT_SOURCE_POOL_SIZE
    source_max_overflow: int = DEFAULT_SOURCE_MAX_OVERFLOW
    source_pool_timeout_seconds: int = DEFAULT_SOURCE_POOL_TIMEOUT_SECONDS
    source_pool_recycle_seconds: int = DEFAULT_SOURCE_POOL_RECYCLE_SECONDS
    index_pool_size: int = DEFAULT_INDEX_POOL_SIZE
    index_max_overflow: int = DEFAULT_INDEX_MAX_OVERFLOW
    index_pool_timeout_seconds: int = DEFAULT_INDEX_POOL_TIMEOUT_SECONDS
    index_pool_recycle_seconds: int = DEFAULT_INDEX_POOL_RECYCLE_SECONDS
    max_correction_retries: int = MAX_ALLOWED_CORRECTION_RETRIES
    max_regeneration_count: int = DEFAULT_MAX_REGENERATION_COUNT
    max_question_length: int = DEFAULT_MAX_QUESTION_LENGTH
    model_request_timeout_seconds: int = DEFAULT_MODEL_REQUEST_TIMEOUT_SECONDS
    max_returned_rows: int = 1000
    max_result_bytes: int = 5_000_000
    query_timeout_seconds: int = 30
    embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE
    embedding_request_timeout_seconds: int = DEFAULT_EMBEDDING_REQUEST_TIMEOUT_SECONDS
    retrieval_vector_candidate_limit: int = DEFAULT_RETRIEVAL_VECTOR_CANDIDATE_LIMIT
    retrieval_keyword_candidate_limit: int = DEFAULT_RETRIEVAL_KEYWORD_CANDIDATE_LIMIT
    retrieval_max_selected_tables: int = DEFAULT_RETRIEVAL_MAX_SELECTED_TABLES
    retrieval_max_columns_per_table: int = DEFAULT_RETRIEVAL_MAX_COLUMNS_PER_TABLE
    retrieval_max_relationships: int = DEFAULT_RETRIEVAL_MAX_RELATIONSHIPS
    retrieval_max_relationship_hops: int = DEFAULT_RETRIEVAL_MAX_RELATIONSHIP_HOPS
    retrieval_max_expanded_tables: int = DEFAULT_RETRIEVAL_MAX_EXPANDED_TABLES
    retrieval_max_context_documents: int = DEFAULT_RETRIEVAL_MAX_CONTEXT_DOCUMENTS
    retrieval_max_context_characters: int = DEFAULT_RETRIEVAL_MAX_CONTEXT_CHARACTERS
    retrieval_min_vector_similarity: float = DEFAULT_RETRIEVAL_MIN_VECTOR_SIMILARITY
    retrieval_vector_weight: float = DEFAULT_RETRIEVAL_VECTOR_WEIGHT
    retrieval_keyword_weight: float = DEFAULT_RETRIEVAL_KEYWORD_WEIGHT
    retrieval_rrf_constant: int = DEFAULT_RETRIEVAL_RRF_CONSTANT
    strict_semantic_metadata: bool = False
    log_level: str = "INFO"
    frontend_origins: str = "http://localhost:5173"

    @field_validator("max_correction_retries")
    @classmethod
    def validate_correction_retries(cls, value: int) -> int:
        if not 0 <= value <= MAX_ALLOWED_CORRECTION_RETRIES:
            raise ValueError("must be between 0 and 2")
        return value

    @field_validator(
        "database_connect_timeout_seconds",
        "source_pool_timeout_seconds",
        "source_pool_recycle_seconds",
        "index_pool_timeout_seconds",
        "index_pool_recycle_seconds",
        "max_returned_rows",
        "max_result_bytes",
        "query_timeout_seconds",
        "max_regeneration_count",
        "max_question_length",
        "model_request_timeout_seconds",
        "embedding_batch_size",
        "embedding_request_timeout_seconds",
        "retrieval_vector_candidate_limit",
        "retrieval_keyword_candidate_limit",
        "retrieval_max_selected_tables",
        "retrieval_max_columns_per_table",
        "retrieval_max_relationships",
        "retrieval_max_relationship_hops",
        "retrieval_max_expanded_tables",
        "retrieval_max_context_documents",
        "retrieval_max_context_characters",
        "retrieval_rrf_constant",
    )
    @classmethod
    def validate_positive_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator(
        "source_pool_size", "source_max_overflow", "index_pool_size", "index_max_overflow"
    )
    @classmethod
    def validate_non_negative_pool_value(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be zero or greater")
        return value

    @field_validator("retrieval_min_vector_similarity")
    @classmethod
    def validate_vector_similarity(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("must be between zero and one")
        return value

    @field_validator("retrieval_vector_weight", "retrieval_keyword_weight")
    @classmethod
    def validate_retrieval_weight(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator(
        "retrieval_vector_candidate_limit",
        "retrieval_keyword_candidate_limit",
        "retrieval_max_selected_tables",
        "retrieval_max_columns_per_table",
        "retrieval_max_relationships",
        "retrieval_max_expanded_tables",
        "retrieval_max_context_documents",
    )
    @classmethod
    def validate_retrieval_bound(cls, value: int) -> int:
        if value > 256:
            raise ValueError("must not exceed 256")
        return value

    @field_validator("retrieval_max_relationship_hops")
    @classmethod
    def validate_relationship_hops(cls, value: int) -> int:
        if value > 1:
            raise ValueError("must not exceed one hop")
        return value

    @field_validator("retrieval_max_context_characters")
    @classmethod
    def validate_context_characters(cls, value: int) -> int:
        if value > 100_000:
            raise ValueError("must not exceed 100000")
        return value

    @field_validator("openrouter_base_url")
    @classmethod
    def validate_openrouter_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("must be an HTTP or HTTPS URL")
        return value.rstrip("/")

    @property
    def source_schema_names(self) -> tuple[str, ...]:
        """Return the configured comma-separated source schemas in stable order."""

        names: list[str] = []
        seen: set[str] = set()
        for raw_name in self.source_schema_scope.split(","):
            name = raw_name.strip()
            if name and name not in seen:
                names.append(name)
                seen.add(name)
        return tuple(names)

    @property
    def model_roles(self) -> tuple[tuple[str, str | None], ...]:
        """Return logical model roles without exposing model credentials."""

        return (
            ("QUESTION_MODEL", self.question_model),
            ("SQL_MODEL", self.sql_model),
            ("SQL_CORRECTION_MODEL", self.sql_correction_model),
            ("ANSWER_MODEL", self.answer_model),
            ("EMBEDDING_MODEL", self.embedding_model),
        )

    def model_id_for(self, role: ModelRole) -> str:
        """Resolve one configured model ID without exposing provider credentials."""

        values = {
            ModelRole.QUESTION_ANALYSIS: self.question_model,
            ModelRole.SQL_GENERATION: self.sql_model,
            ModelRole.SQL_CORRECTION: self.sql_correction_model,
            ModelRole.ANSWER_GENERATION: self.answer_model,
            ModelRole.EMBEDDING: self.embedding_model,
        }
        model_id = values[role]
        if model_id is None or not model_id.strip():
            raise ValueError(f"{role.value} model is not configured.")
        return model_id.strip()

    def configuration_issues(
        self, *, require_openrouter: bool = False
    ) -> tuple[ConfigurationIssue, ...]:
        """Return safe configuration issues for startup or an operation boundary."""

        issues: list[ConfigurationIssue] = []
        self._add_required_secret_issue(issues, "SOURCE_DATABASE_URL", self.source_database_url)
        self._add_required_secret_issue(issues, "INDEX_DATABASE_URL", self.index_database_url)

        if self.source_database_url is not None and self._has_secret(self.source_database_url):
            self._add_postgres_url_issue(issues, "SOURCE_DATABASE_URL", self.source_database_url)
        if self.index_database_url is not None and self._has_secret(self.index_database_url):
            self._add_postgres_url_issue(issues, "INDEX_DATABASE_URL", self.index_database_url)

        if self.source_database_url and self.index_database_url:
            if (
                self.source_database_url.get_secret_value()
                == self.index_database_url.get_secret_value()
            ):
                issues.append(
                    ConfigurationIssue(
                        "DATABASE_URLS",
                        "same_database",
                        "SOURCE_DATABASE_URL and INDEX_DATABASE_URL must be different.",
                    )
                )

        if not self.source_schema_names:
            issues.append(
                ConfigurationIssue(
                    "SOURCE_SCHEMA_SCOPE",
                    "missing",
                    "SOURCE_SCHEMA_SCOPE must contain at least one schema name.",
                )
            )
        for schema_name in self.source_schema_names:
            if schema_name.lower() in SYSTEM_SCHEMAS or schema_name.lower().startswith(
                ("pg_temp_", "pg_toast_temp_")
            ):
                issues.append(
                    ConfigurationIssue(
                        "SOURCE_SCHEMA_SCOPE",
                        "system_schema",
                        (
                            "SOURCE_SCHEMA_SCOPE cannot include PostgreSQL system schema "
                            f"'{schema_name}'."
                        ),
                    )
                )

        for role_name, model_name in self.model_roles:
            if not model_name or not model_name.strip():
                issues.append(
                    ConfigurationIssue(
                        role_name,
                        "missing",
                        f"{role_name} is required for normal model operations.",
                    )
                )

        if require_openrouter and not self._has_secret(self.openrouter_api_key):
            issues.append(
                ConfigurationIssue(
                    "OPENROUTER_API_KEY",
                    "missing",
                    "OPENROUTER_API_KEY is required for model operations.",
                )
            )

        return tuple(issues)

    def validate_for_runtime(self, *, require_openrouter: bool = True) -> None:
        """Raise a safe error when configuration cannot support runtime work."""

        issues = self.configuration_issues(require_openrouter=require_openrouter)
        if issues:
            raise ConfigurationError(issues)

    @staticmethod
    def _has_secret(value: SecretStr | None) -> bool:
        return value is not None and bool(value.get_secret_value().strip())

    @classmethod
    def _add_required_secret_issue(
        cls,
        issues: list[ConfigurationIssue],
        field: str,
        value: SecretStr | None,
    ) -> None:
        if not cls._has_secret(value):
            issues.append(
                ConfigurationIssue(field, "missing", f"{field} is required for backend operation.")
            )

    @staticmethod
    def _add_postgres_url_issue(
        issues: list[ConfigurationIssue], field: str, value: SecretStr
    ) -> None:
        try:
            parsed_url = make_url(value.get_secret_value())
        except (ArgumentError, TypeError, ValueError):
            parsed_url = None

        if parsed_url is None or not parsed_url.drivername.startswith("postgresql"):
            issues.append(
                ConfigurationIssue(field, "invalid_url", f"{field} must be a PostgreSQL URL.")
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings singleton."""

    return Settings()
