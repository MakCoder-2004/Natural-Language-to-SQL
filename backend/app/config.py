"""Typed application settings and safe startup configuration validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_SOURCE_SCHEMA_SCOPE: Final[str] = "public"
MAX_ALLOWED_CORRECTION_RETRIES: Final[int] = 2
SYSTEM_SCHEMAS: Final[frozenset[str]] = frozenset({"information_schema", "pg_catalog", "pg_toast"})


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

    question_model: str | None = None
    sql_model: str | None = None
    sql_correction_model: str | None = None
    answer_model: str | None = None
    embedding_model: str | None = None

    source_schema_scope: str = DEFAULT_SOURCE_SCHEMA_SCOPE
    max_correction_retries: int = MAX_ALLOWED_CORRECTION_RETRIES
    max_returned_rows: int = 1000
    max_result_bytes: int = 5_000_000
    query_timeout_seconds: int = 30
    log_level: str = "INFO"
    frontend_origins: str = "http://localhost:5173"

    @field_validator("max_correction_retries")
    @classmethod
    def validate_correction_retries(cls, value: int) -> int:
        if not 0 <= value <= MAX_ALLOWED_CORRECTION_RETRIES:
            raise ValueError("must be between 0 and 2")
        return value

    @field_validator("max_returned_rows", "max_result_bytes", "query_timeout_seconds")
    @classmethod
    def validate_positive_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
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

        return tuple(name.strip() for name in self.source_schema_scope.split(",") if name.strip())

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
