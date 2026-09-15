"""Single-user runtime management for the external source database."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from pydantic import SecretStr
from sqlalchemy.engine import URL, make_url

from app.config import Settings
from app.database.errors import DatabasePermissionError, DatabaseServiceError
from app.database.models import SourceSchemaSnapshot
from app.database.services import DatabaseServices
from app.database.source_connection import SourceDatabase, create_source_database
from app.database.source_introspection import SourceIntrospector
from app.database.source_permissions import verify_source_read_only_access


@dataclass(frozen=True, slots=True)
class SourceConnectionProfile:
    """Safe source identity and access information for the settings UI."""

    host: str
    port: int | None
    database: str | None
    user: str | None
    schemas: tuple[str, ...]
    relation_count: int
    read_only_verified: bool


class RuntimeDatabaseManager:
    """Replace the in-memory source binding without touching the index binding."""

    def __init__(self, settings: Settings, services: DatabaseServices) -> None:
        self.settings = settings
        self.services = services
        self._lock = RLock()

    def test(self, url: str, schema_scope: str) -> SourceConnectionProfile:
        candidate, candidate_settings = self._candidate(url, schema_scope)
        try:
            snapshot = SourceIntrospector(candidate).introspect()
            verify_source_read_only_access(candidate, snapshot)
            return _profile(candidate_settings, snapshot)
        finally:
            candidate.dispose()

    def save(self, url: str, schema_scope: str) -> SourceConnectionProfile:
        candidate, candidate_settings = self._candidate(url, schema_scope)
        try:
            snapshot = SourceIntrospector(candidate).introspect()
            verify_source_read_only_access(candidate, snapshot)
            profile = _profile(candidate_settings, snapshot)
            with self._lock:
                previous = self.services.source
                self.services.source = candidate
                self.settings.source_database_url = candidate_settings.source_database_url
                self.settings.source_schema_scope = candidate_settings.source_schema_scope
                if previous is not None:
                    previous.dispose()
            return profile
        except Exception:
            candidate.dispose()
            raise

    def disconnect(self) -> None:
        with self._lock:
            previous = self.services.source
            self.services.source = None
            self.settings.source_database_url = None
            if previous is not None:
                previous.dispose()

    def _candidate(self, url: str, schema_scope: str) -> tuple[SourceDatabase, Settings]:
        value = url.strip()
        if not value:
            raise DatabaseServiceError("A PostgreSQL connection URL is required.")
        try:
            parsed = make_url(value)
        except (TypeError, ValueError) as exc:
            raise DatabaseServiceError("The connection URL is invalid.") from exc
        if not parsed.drivername.startswith("postgresql"):
            raise DatabaseServiceError("The connection URL must use PostgreSQL.")
        if parsed.host in {"index-db", "index_db"}:
            raise DatabasePermissionError("The local schema index cannot be used as a source.")
        if not schema_scope.strip():
            raise DatabaseServiceError("At least one source schema is required.")
        candidate_settings = self.settings.model_copy(
            update={
                "source_database_url": SecretStr(value),
                "source_schema_scope": schema_scope.strip(),
            }
        )
        candidate = create_source_database(candidate_settings)
        return candidate, candidate_settings


def _profile(settings: Settings, snapshot: SourceSchemaSnapshot) -> SourceConnectionProfile:
    identity = snapshot.identity
    schemas = snapshot.schemas
    return SourceConnectionProfile(
        host=_safe_host(settings.source_database_url),
        port=_safe_url(settings.source_database_url).port,
        database=identity.database_name,
        user=identity.user_name,
        schemas=tuple(schema.name for schema in schemas),
        relation_count=sum(len(schema.relations) for schema in schemas),
        read_only_verified=True,
    )


def _safe_url(value: SecretStr | None) -> URL:
    if value is None:
        raise DatabaseServiceError("The source database is not configured.")
    return make_url(value.get_secret_value())


def _safe_host(value: SecretStr | None) -> str:
    return _safe_url(value).host or "unknown"
