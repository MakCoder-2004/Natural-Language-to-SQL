"""Command-line entry point for a complete schema index refresh."""

from __future__ import annotations

import logging
import sys

from app.config import get_settings
from app.database.errors import DatabaseServiceError, IndexServiceError
from app.database.services import create_database_services
from app.services.indexing_service import IndexingService


def main() -> int:
    """Run indexing and print only safe run metadata."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    database_services = None
    try:
        database_services = create_database_services(settings)
        run = IndexingService(settings, database_services).run()
        print(
            f"schema index run {run.run_id}: {run.status}; "
            f"documents={run.document_count}; embeddings={run.embedding_count}"
        )
        return 0
    except (DatabaseServiceError, IndexServiceError) as exc:
        print(f"schema indexing failed: {exc.error_code}", file=sys.stderr)
        return 1
    finally:
        if database_services is not None:
            database_services.dispose()
