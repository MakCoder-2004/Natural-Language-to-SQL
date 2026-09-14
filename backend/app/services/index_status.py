"""Read-only schema-index readiness and freshness status."""

from __future__ import annotations

from typing import Literal

from app.config import Settings
from app.database.errors import DatabaseServiceError, IndexServiceError
from app.database.index_repository import IndexRepository
from app.database.services import DatabaseServices
from app.database.source_introspection import SourceIntrospector
from app.models.health import HealthComponent
from app.models.schema_index import IndexRunRecord
from app.retrieval.schema_documents import source_index_key
from app.retrieval.semantic_metadata import load_semantic_metadata


def build_schema_index_health(
    settings: Settings,
    database_services: DatabaseServices | None,
    *,
    source_component: HealthComponent,
    index_component: HealthComponent,
) -> HealthComponent:
    """Compare the active local index with a live technical source snapshot."""

    if not index_component.configured:
        return HealthComponent(
            status="not_initialized",
            configured=False,
            detail="Schema-index database settings are not configured.",
            freshness_checked=False,
        )
    if database_services is None or database_services.index is None:
        return HealthComponent(
            status="not_initialized",
            configured=True,
            detail="Schema indexing has not been initialized.",
            reachable=index_component.reachable,
            freshness_checked=False,
        )
    if source_component.status != "reachable":
        return HealthComponent(
            status="unavailable",
            configured=True,
            detail="Source freshness cannot be checked while the source database is unavailable.",
            reachable=index_component.reachable,
            freshness_checked=False,
        )
    if index_component.status != "reachable":
        return HealthComponent(
            status="unavailable",
            configured=True,
            detail=(
                "Schema-index freshness cannot be checked while the index database is unavailable."
            ),
            reachable=False,
            freshness_checked=False,
        )

    try:
        if database_services.source is None:
            raise IndexServiceError("The source database is not configured.")
        snapshot = SourceIntrospector(database_services.source).introspect()
        source_key = source_index_key(snapshot)
        repository = IndexRepository(database_services.index)
        latest_run = repository.latest_run(source_key)
        successful_run = repository.latest_run(source_key, status="succeeded")
        if latest_run is None:
            return HealthComponent(
                status="not_initialized",
                configured=True,
                detail="No schema index run has completed.",
                reachable=True,
                freshness_checked=True,
            )
        if latest_run.status == "failed" and successful_run is None:
            return _run_component(
                status="failed",
                detail="The latest schema index run failed.",
                run=latest_run,
            )
        if successful_run is None:
            return _run_component(
                status="failed",
                detail="No successful schema index run is available.",
                run=latest_run,
            )

        semantic_digest = load_semantic_metadata(settings.semantic_metadata_path).digest
        active_documents = repository.list_active_documents(source_key)
        matches = (
            successful_run.source_fingerprint == snapshot.fingerprint
            and successful_run.semantic_metadata_digest == semantic_digest
            and successful_run.document_count == len(active_documents)
        )
        if latest_run.status == "failed":
            return _run_component(
                status="failed",
                detail="The latest refresh failed; the previous active index remains available.",
                run=latest_run,
                active_document_count=len(active_documents),
            )
        return _run_component(
            status="ready" if matches else "stale",
            detail=(
                "The schema index matches the current source and semantic metadata."
                if matches
                else "The schema index is stale and must be refreshed."
            ),
            run=successful_run,
            active_document_count=len(active_documents),
        )
    except DatabaseServiceError:
        return HealthComponent(
            status="unavailable",
            configured=True,
            detail="Schema-index freshness could not be checked safely.",
            reachable=True,
            freshness_checked=False,
        )
    except IndexServiceError:
        return HealthComponent(
            status="not_initialized",
            configured=True,
            detail="Schema-index storage has not been initialized.",
            reachable=True,
            freshness_checked=False,
        )


def _run_component(
    *,
    status: LiteralStatus,
    detail: str,
    run: IndexRunRecord,
    active_document_count: int | None = None,
) -> HealthComponent:
    return HealthComponent(
        status=status,
        configured=True,
        detail=detail,
        reachable=True,
        freshness_checked=True,
        source_fingerprint=run.source_fingerprint,
        semantic_metadata_digest=run.semantic_metadata_digest,
        indexed_at=run.finished_at,
        document_count=(
            active_document_count if active_document_count is not None else run.document_count
        ),
        embedding_model=run.embedding_model,
    )


LiteralStatus = Literal["ready", "stale", "failed"]
