"""Explicitly separated database service collection and lifecycle helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.database.index_connection import IndexDatabase, create_index_database
from app.database.source_connection import SourceDatabase, create_source_database


@dataclass(slots=True)
class DatabaseServices:
    """Application-owned source and index services with explicit boundaries."""

    source: SourceDatabase | None = None
    index: IndexDatabase | None = None

    def dispose(self) -> None:
        """Dispose both database engines during application shutdown."""

        if self.source is not None:
            self.source.dispose()
        if self.index is not None:
            self.index.dispose()

    def replace_source(self, source: SourceDatabase | None) -> SourceDatabase | None:
        """Replace the source binding and return the previous service."""

        previous = self.source
        self.source = source
        return previous


def create_database_services(settings: Settings) -> DatabaseServices:
    """Create configured database services without connecting eagerly."""

    services = DatabaseServices()
    try:
        if (
            settings.source_database_url is not None
            and settings.source_database_url.get_secret_value().strip()
        ):
            services.source = create_source_database(settings)
        if (
            settings.index_database_url is not None
            and settings.index_database_url.get_secret_value().strip()
        ):
            services.index = create_index_database(settings)
    except Exception:
        services.dispose()
        raise
    return services
