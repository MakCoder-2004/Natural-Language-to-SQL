"""Bounded hybrid schema retrieval orchestration."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from time import perf_counter

from langchain_core.documents import Document

from app.config import Settings
from app.database.errors import IndexReadinessError, NoRelevantSchemaError
from app.database.index_repository import IndexRepository
from app.database.services import DatabaseServices
from app.models.retrieval import (
    RankedSchemaDocument,
    RetrievalDiagnostics,
    RetrievalLimits,
    RetrievalResult,
    RetrievedColumn,
    RetrievedIndexDocument,
    RetrievedRelationship,
    RetrievedTable,
)
from app.retrieval.context import SchemaContextBuilder
from app.retrieval.embeddings import EmbeddingProvider, create_embedding_provider
from app.retrieval.ranking import fuse_documents
from app.retrieval.retrievers import (
    KeywordSchemaRetriever,
    VectorSchemaRetriever,
    document_from_indexed_document,
)
from app.services.index_status import require_ready_schema_index

logger = logging.getLogger(__name__)
_REPOSITORY_LIMIT = 256
_CATEGORY_WEIGHTS: dict[str, float] = {
    "table": 1.0,
    "semantic_concept": 0.95,
    "column": 0.85,
    "relationship": 0.75,
}


@dataclass(slots=True)
class _TableCandidate:
    key: tuple[str, str]
    score: float
    direct: bool = True
    evidence: list[RankedSchemaDocument] = field(default_factory=list)
    table_document: RetrievedIndexDocument | None = None


@dataclass(frozen=True, slots=True)
class _RelationshipCandidate:
    document: RetrievedIndexDocument
    score: float
    directly_retrieved: bool


class HybridSchemaRetrievalService:
    """Retrieve compact schema context using two bounded LangChain signals."""

    def __init__(
        self,
        settings: Settings,
        database_services: DatabaseServices | None,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.settings = settings
        self.database_services = database_services
        self.embedding_provider = embedding_provider

    def retrieve(self, question: str) -> RetrievalResult:
        """Return relevant schema context and log safe failure telemetry."""

        try:
            return self._retrieve(question)
        except Exception as exc:
            error_code = getattr(exc, "error_code", "retrieval_failed")
            reason = getattr(exc, "reason", None)
            logger.warning(
                "schema_retrieval_failed error_code=%s reason=%s",
                error_code if isinstance(error_code, str) else "retrieval_failed",
                reason if isinstance(reason, str) else "unknown",
            )
            raise

    def _retrieve(self, question: str) -> RetrievalResult:
        """Return relevant schema context or fail safely without guessing."""

        if not question.strip():
            raise NoRelevantSchemaError("A non-empty question is required for schema retrieval.")
        started = perf_counter()
        readiness_started = perf_counter()
        readiness = require_ready_schema_index(self.settings, self.database_services)
        stage_latency = {"readiness": _milliseconds(readiness_started)}
        if self.database_services is None or self.database_services.index is None:
            raise IndexReadinessError(
                "The schema index is not available for retrieval.",
                reason="index_unavailable",
            )

        provider = self.embedding_provider or create_embedding_provider(self.settings)
        repository = IndexRepository(self.database_services.index)
        limits = _retrieval_limits(self.settings)
        vector_retriever = VectorSchemaRetriever(
            repository=repository,
            embedding_provider=provider,
            source_key=readiness.source_key,
            source_fingerprint=readiness.source_fingerprint,
            embedding_model=readiness.embedding_model,
            embedding_dimension=readiness.embedding_dimension,
            limit=limits.vector_candidate_limit,
            minimum_similarity=limits.min_vector_similarity,
        )
        keyword_retriever = KeywordSchemaRetriever(
            repository=repository,
            source_key=readiness.source_key,
            source_fingerprint=readiness.source_fingerprint,
            limit=limits.keyword_candidate_limit,
        )

        vector_started = perf_counter()
        vector_documents = vector_retriever.invoke(question)
        stage_latency["vector"] = _milliseconds(vector_started)
        keyword_started = perf_counter()
        keyword_documents = keyword_retriever.invoke(question)
        stage_latency["keyword"] = _milliseconds(keyword_started)

        fusion_started = perf_counter()
        ranked_documents = fuse_documents(
            vector_documents,
            keyword_documents,
            vector_weight=limits.vector_weight,
            keyword_weight=limits.keyword_weight,
            rrf_constant=limits.rrf_constant,
        )
        stage_latency["fusion"] = _milliseconds(fusion_started)
        if not ranked_documents:
            raise NoRelevantSchemaError("No credible schema context matched the question.")

        ranking_started = perf_counter()
        table_candidates = _rank_table_candidates(ranked_documents)
        selected_tables = table_candidates[: limits.max_selected_tables]
        if not selected_tables:
            raise NoRelevantSchemaError("No credible source tables matched the question.")
        stage_latency["table_ranking"] = _milliseconds(ranking_started)

        expansion_started = perf_counter()
        relation_keys = tuple(candidate.key for candidate in selected_tables)
        table_documents = repository.list_active_relation_documents(
            readiness.source_key,
            readiness.source_fingerprint,
            relation_keys,
            category="table",
            limit=_repository_limit(len(relation_keys)),
        )
        for document in table_documents:
            candidate = _candidate_for_key(selected_tables, _relation_key(document))
            if candidate is not None:
                candidate.table_document = document

        relationship_candidates = _relationship_candidates(
            ranked_documents,
            selected_tables,
            repository,
            readiness.source_key,
            readiness.source_fingerprint,
            limits,
        )
        selected_relationships, expanded_keys = _select_relationships(
            relationship_candidates,
            selected_tables,
            limits,
        )
        all_relation_keys = relation_keys + tuple(
            key for key in expanded_keys if key not in relation_keys
        )
        expanded_table_documents = repository.list_active_relation_documents(
            readiness.source_key,
            readiness.source_fingerprint,
            expanded_keys,
            category="table",
            limit=_repository_limit(len(expanded_keys)),
        )
        all_table_documents = table_documents + tuple(
            document
            for document in expanded_table_documents
            if document.document_key not in {item.document_key for item in table_documents}
        )
        for document in all_table_documents:
            candidate = _candidate_for_key(selected_tables, _relation_key(document))
            if candidate is None:
                candidate = _expanded_candidate(document, selected_relationships)
                if candidate is not None:
                    selected_tables = (*selected_tables, candidate)
            if candidate is not None:
                candidate.table_document = document
        stage_latency["relationship_expansion"] = _milliseconds(expansion_started)

        columns_started = perf_counter()
        column_documents = repository.list_active_relation_documents(
            readiness.source_key,
            readiness.source_fingerprint,
            all_relation_keys,
            category="column",
            limit=_repository_limit(len(all_relation_keys) * limits.max_columns_per_table),
        )
        columns_by_relation: dict[tuple[str, str], list[RetrievedIndexDocument]] = defaultdict(list)
        for document in column_documents:
            columns_by_relation[_relation_key(document)].append(document)
        ranked_columns = _ranked_columns_by_relation(ranked_documents)
        selected_table_models: list[RetrievedTable] = []
        selected_column_models: list[RetrievedColumn] = []
        for candidate in selected_tables:
            selected_columns = _select_columns(
                candidate,
                columns_by_relation.get(candidate.key, ()),
                ranked_columns.get(candidate.key, ()),
                selected_relationships,
                limits.max_columns_per_table,
            )
            table_model = _table_model(candidate, selected_columns)
            selected_table_models.append(table_model)
            selected_column_models.extend(selected_columns)
        stage_latency["column_selection"] = _milliseconds(columns_started)

        context_started = perf_counter()
        semantic_definitions = _semantic_definitions(ranked_documents, selected_tables)
        context_text = SchemaContextBuilder().build(
            index_fingerprint=readiness.source_fingerprint,
            tables=selected_table_models,
            relationships=selected_relationships,
            semantic_definitions=semantic_definitions,
            max_documents=limits.max_context_documents,
            max_characters=limits.max_context_characters,
        )
        if not context_text or "Table:" not in context_text:
            raise NoRelevantSchemaError("No compact schema context could be constructed.")
        stage_latency["context"] = _milliseconds(context_started)

        selected_documents = _selected_documents(
            selected_tables,
            selected_relationships,
            ranked_documents,
            selected_column_models,
            column_documents,
            relationship_candidates,
        )
        diagnostics = RetrievalDiagnostics(
            vector_candidate_count=len(vector_documents),
            keyword_candidate_count=len(keyword_documents),
            fused_candidate_count=len(ranked_documents),
            selected_table_count=len(selected_table_models),
            selected_column_count=len(selected_column_models),
            relationship_count=len(selected_relationships),
            expanded_table_count=sum(not table.direct for table in selected_table_models),
            stage_latency_ms={**stage_latency, "total": _milliseconds(started)},
            limits=limits,
        )
        logger.info(
            "schema_retrieval_completed source_fingerprint=%s vector_candidates=%d "
            "keyword_candidates=%d selected_tables=%d selected_columns=%d relationships=%d "
            "latency_ms=%.3f",
            readiness.source_fingerprint,
            len(vector_documents),
            len(keyword_documents),
            len(selected_table_models),
            len(selected_column_models),
            len(selected_relationships),
            diagnostics.stage_latency_ms["total"],
        )
        return RetrievalResult(
            documents=tuple(selected_documents),
            tables=tuple(selected_table_models),
            columns=tuple(selected_column_models),
            relationships=tuple(selected_relationships),
            context_text=context_text,
            index_fingerprint=readiness.source_fingerprint,
            diagnostics=diagnostics,
        )


def _retrieval_limits(settings: Settings) -> RetrievalLimits:
    return RetrievalLimits(
        vector_candidate_limit=min(settings.retrieval_vector_candidate_limit, _REPOSITORY_LIMIT),
        keyword_candidate_limit=min(settings.retrieval_keyword_candidate_limit, _REPOSITORY_LIMIT),
        max_selected_tables=settings.retrieval_max_selected_tables,
        max_columns_per_table=settings.retrieval_max_columns_per_table,
        max_relationships=settings.retrieval_max_relationships,
        max_relationship_hops=settings.retrieval_max_relationship_hops,
        max_expanded_tables=settings.retrieval_max_expanded_tables,
        max_context_documents=settings.retrieval_max_context_documents,
        max_context_characters=settings.retrieval_max_context_characters,
        min_vector_similarity=settings.retrieval_min_vector_similarity,
        vector_weight=settings.retrieval_vector_weight,
        keyword_weight=settings.retrieval_keyword_weight,
        rrf_constant=settings.retrieval_rrf_constant,
    )


def _rank_table_candidates(
    documents: Sequence[RankedSchemaDocument],
) -> tuple[_TableCandidate, ...]:
    candidates: dict[tuple[str, str], _TableCandidate] = {}
    for ranked in documents:
        key = _relation_key(ranked.document)
        weight = _CATEGORY_WEIGHTS.get(ranked.document.category)
        if weight is None or ranked.document.relation_name is None:
            continue
        candidate = candidates.setdefault(key, _TableCandidate(key, 0.0))
        evidence_score = ranked.fused_score * weight
        if len(ranked.signals) > 1:
            evidence_score += 0.002
        if ranked.document.category == "table":
            evidence_score += 0.001
        candidate.score = max(candidate.score, evidence_score)
        candidate.evidence.append(ranked)
        if ranked.document.category == "table" and candidate.table_document is None:
            candidate.table_document = ranked.document
    return tuple(
        sorted(
            candidates.values(),
            key=lambda candidate: (
                -candidate.score,
                -len({signal for item in candidate.evidence for signal in item.signals}),
                candidate.key[0],
                candidate.key[1],
            ),
        )
    )


def _relationship_candidates(
    ranked_documents: Sequence[RankedSchemaDocument],
    selected_tables: Sequence[_TableCandidate],
    repository: IndexRepository,
    source_key: str,
    source_fingerprint: str,
    limits: RetrievalLimits,
) -> tuple[_RelationshipCandidate, ...]:
    selected_keys = {candidate.key for candidate in selected_tables}
    direct: dict[str, _RelationshipCandidate] = {}
    for ranked in ranked_documents:
        if ranked.document.category != "relationship":
            continue
        if not _relationship_touches(ranked.document, selected_keys):
            continue
        direct[ranked.document.document_key] = _RelationshipCandidate(
            ranked.document, ranked.fused_score, True
        )

    relation_keys = tuple(selected_keys)
    related_documents = list(
        repository.list_active_relationship_documents(
            source_key,
            source_fingerprint,
            relation_keys,
            direction="outgoing",
            limit=_repository_limit(max(1, limits.max_relationships * 2)),
        )
    )
    related_documents.extend(
        repository.list_active_relationship_documents(
            source_key,
            source_fingerprint,
            relation_keys,
            direction="incoming",
            limit=_repository_limit(max(1, limits.max_relationships * 2)),
        )
    )
    table_scores = {candidate.key: candidate.score for candidate in selected_tables}
    for document in related_documents:
        if document.document_key in direct:
            continue
        source_relation = _relation_key(document)
        target_relation = _target_relation_key(document)
        supporting_score = max(
            table_scores.get(source_relation, 0.0), table_scores.get(target_relation, 0.0)
        )
        if supporting_score <= 0.0:
            continue
        direct[document.document_key] = _RelationshipCandidate(
            document,
            supporting_score * _CATEGORY_WEIGHTS["relationship"],
            False,
        )
    return tuple(
        sorted(
            direct.values(),
            key=lambda candidate: (
                -candidate.score,
                not candidate.directly_retrieved,
                candidate.document.qualified_identifier,
                candidate.document.document_key,
            ),
        )
    )


def _select_relationships(
    candidates: Sequence[_RelationshipCandidate],
    selected_tables: Sequence[_TableCandidate],
    limits: RetrievalLimits,
) -> tuple[tuple[RetrievedRelationship, ...], tuple[tuple[str, str], ...]]:
    if limits.max_relationship_hops < 1:
        return (), ()
    selected_keys = {candidate.key for candidate in selected_tables}
    direct_edges: list[_RelationshipCandidate] = []
    expansion_edges: list[_RelationshipCandidate] = []
    for candidate in candidates:
        source = _relation_key(candidate.document)
        target = _target_relation_key(candidate.document)
        if source in selected_keys and target in selected_keys:
            direct_edges.append(candidate)
        else:
            expansion_edges.append(candidate)

    expanded_keys: list[tuple[str, str]] = []
    for candidate in expansion_edges:
        source = _relation_key(candidate.document)
        target = _target_relation_key(candidate.document)
        neighbor = target if source in selected_keys else source
        if neighbor not in expanded_keys and len(expanded_keys) < limits.max_expanded_tables:
            expanded_keys.append(neighbor)
    allowed_expanded = set(expanded_keys)
    chosen = direct_edges + [
        candidate
        for candidate in expansion_edges
        if (
            _target_relation_key(candidate.document) in allowed_expanded
            or _relation_key(candidate.document) in allowed_expanded
        )
    ]
    chosen = chosen[: limits.max_relationships]
    relationships = tuple(
        _relationship_model(candidate, candidate not in direct_edges) for candidate in chosen
    )
    return relationships, tuple(expanded_keys)


def _relationship_model(
    candidate: _RelationshipCandidate,
    expanded: bool,
) -> RetrievedRelationship:
    document = candidate.document
    return RetrievedRelationship(
        source_schema_name=document.schema_name,
        source_relation_name=document.relation_name or "",
        source_columns=_string_tuple(document.metadata.get("source_columns")),
        target_schema_name=document.target_schema_name or "",
        target_relation_name=document.target_relation_name or "",
        target_columns=document.target_column_names,
        cardinality=_optional_string(document.metadata.get("cardinality")),
        description=_description(document.metadata.get("semantic_description"))
        or _content_value(document.content, "Description"),
        score=candidate.score,
        expanded=expanded,
        document_key=document.document_key,
    )


def _select_columns(
    candidate: _TableCandidate,
    column_documents: Sequence[RetrievedIndexDocument],
    ranked_columns: Sequence[RankedSchemaDocument],
    relationships: Sequence[RetrievedRelationship],
    limit: int,
) -> tuple[RetrievedColumn, ...]:
    by_name = {document.column_name: document for document in column_documents}
    ranked_by_name = {document.document.column_name: document for document in ranked_columns}
    required_names: set[str] = set()
    if candidate.table_document is not None:
        required_names.update(_string_tuple(candidate.table_document.metadata.get("primary_key")))
    for relationship in relationships:
        if (relationship.source_schema_name, relationship.source_relation_name) == candidate.key:
            required_names.update(relationship.source_columns)
        if (relationship.target_schema_name, relationship.target_relation_name) == candidate.key:
            required_names.update(relationship.target_columns)

    names = set(ranked_by_name) | required_names
    ordered_names = sorted(
        names,
        key=lambda name: (
            name not in required_names,
            -(ranked_by_name[name].fused_score if name in ranked_by_name else 0.0),
            name,
        ),
    )
    selected: list[RetrievedColumn] = []
    for name in ordered_names:
        document = by_name.get(name)
        ranked = ranked_by_name.get(name)
        if document is None and ranked is not None:
            document = ranked.document
        if document is None:
            continue
        selected.append(
            _column_model(
                document,
                score=ranked.fused_score if ranked is not None else candidate.score * 0.75,
                required=name in required_names,
            )
        )
        if len(selected) >= limit:
            break
    return tuple(selected)


def _table_model(
    candidate: _TableCandidate,
    columns: Sequence[RetrievedColumn],
) -> RetrievedTable:
    document = candidate.table_document
    metadata = document.metadata if document is not None else {}
    return RetrievedTable(
        schema_name=candidate.key[0],
        relation_name=candidate.key[1],
        relation_kind=_optional_string(metadata.get("relation_kind")),
        description=(
            _description(metadata.get("semantic_description"))
            or _description(metadata.get("technical_description"))
            or _description(metadata.get("schema_description"))
        ),
        score=candidate.score,
        direct=candidate.direct,
        evidence_document_keys=tuple(item.document.document_key for item in candidate.evidence),
        columns=tuple(columns),
    )


def _column_model(
    document: RetrievedIndexDocument,
    *,
    score: float,
    required: bool,
) -> RetrievedColumn:
    metadata = document.metadata
    return RetrievedColumn(
        schema_name=document.schema_name,
        relation_name=document.relation_name or "",
        column_name=document.column_name or "",
        data_type=_optional_string(metadata.get("data_type")),
        nullable=metadata.get("nullable") if isinstance(metadata.get("nullable"), bool) else None,
        description=(
            _description(metadata.get("semantic_description"))
            or _description(metadata.get("technical_description"))
            or _content_value(document.content, "Description")
        ),
        roles=_string_tuple(metadata.get("constraint_roles")),
        score=score,
        required=required,
    )


def _ranked_columns_by_relation(
    documents: Sequence[RankedSchemaDocument],
) -> dict[tuple[str, str], tuple[RankedSchemaDocument, ...]]:
    grouped: dict[tuple[str, str], list[RankedSchemaDocument]] = defaultdict(list)
    for document in documents:
        if document.document.category == "column" and document.document.relation_name is not None:
            grouped[_relation_key(document.document)].append(document)
    return {key: tuple(value) for key, value in grouped.items()}


def _semantic_definitions(
    documents: Sequence[RankedSchemaDocument],
    selected_tables: Sequence[_TableCandidate],
) -> tuple[tuple[str, str, str], ...]:
    selected_keys = {candidate.key for candidate in selected_tables}
    definitions: dict[tuple[str, str], tuple[str, str, str]] = {}
    for ranked in documents:
        document = ranked.document
        if document.category != "semantic_concept" or _relation_key(document) not in selected_keys:
            continue
        name = _optional_string(document.metadata.get("concept_name"))
        description = _content_value(document.content, "Description")
        if name and description:
            definitions[(document.document_key, name)] = (
                f"{document.schema_name}.{document.relation_name}",
                name,
                description,
            )
    return tuple(sorted(definitions.values()))


def _selected_documents(
    selected_tables: Sequence[_TableCandidate],
    relationships: Sequence[RetrievedRelationship],
    ranked_documents: Sequence[RankedSchemaDocument],
    columns: Sequence[RetrievedColumn],
    column_documents: Sequence[RetrievedIndexDocument],
    relationship_candidates: Sequence[_RelationshipCandidate],
) -> tuple[Document, ...]:
    documents: dict[str, RetrievedIndexDocument] = {}
    selected_relations = {(table.key[0], table.key[1]) for table in selected_tables}
    for candidate in selected_tables:
        if candidate.table_document is not None:
            documents[candidate.table_document.document_key] = candidate.table_document
    for ranked in ranked_documents:
        document = ranked.document
        if (
            document.category == "semantic_concept"
            and _relation_key(document) in selected_relations
        ):
            documents[document.document_key] = document
    relationship_documents = {
        candidate.document.document_key: candidate.document for candidate in relationship_candidates
    }
    for relationship in relationships:
        relationship_document = relationship_documents.get(relationship.document_key)
        if relationship_document is not None:
            documents[relationship.document_key] = relationship_document
    for column in columns:
        matching = next(
            (
                document
                for document in column_documents
                if document.column_name == column.column_name
                and _relation_key(document) == (column.schema_name, column.relation_name)
            ),
            None,
        )
        if matching is not None:
            documents[matching.document_key] = matching
            continue
        for ranked in ranked_documents:
            if (
                ranked.document.category == "column"
                and ranked.document.column_name == column.column_name
                and _relation_key(ranked.document) == (column.schema_name, column.relation_name)
            ):
                documents[ranked.document.document_key] = ranked.document
                break
    return tuple(
        document_from_indexed_document(document)
        for document in sorted(documents.values(), key=lambda item: item.qualified_identifier)
    )


def _expanded_candidate(
    document: RetrievedIndexDocument,
    relationships: Sequence[RetrievedRelationship],
) -> _TableCandidate | None:
    key = _relation_key(document)
    supporting = [
        relationship.score
        for relationship in relationships
        if (relationship.source_schema_name, relationship.source_relation_name) == key
        or (relationship.target_schema_name, relationship.target_relation_name) == key
    ]
    if not supporting:
        return None
    return _TableCandidate(
        key,
        max(supporting) * 0.75,
        direct=False,
        table_document=document,
    )


def _candidate_for_key(
    candidates: Sequence[_TableCandidate], key: tuple[str, str]
) -> _TableCandidate | None:
    return next((candidate for candidate in candidates if candidate.key == key), None)


def _relationship_touches(document: RetrievedIndexDocument, keys: set[tuple[str, str]]) -> bool:
    return _relation_key(document) in keys or _target_relation_key(document) in keys


def _relation_key(document: RetrievedIndexDocument) -> tuple[str, str]:
    return document.schema_name, document.relation_name or ""


def _target_relation_key(document: RetrievedIndexDocument) -> tuple[str, str]:
    return document.target_schema_name or "", document.target_relation_name or ""


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _description(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _content_value(content: str, label: str) -> str | None:
    prefix = f"{label}:"
    for line in content.splitlines():
        if line.startswith(prefix):
            return _description(line[len(prefix) :])
    return None


def _repository_limit(value: int) -> int:
    return max(1, min(value, _REPOSITORY_LIMIT))


def _milliseconds(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
