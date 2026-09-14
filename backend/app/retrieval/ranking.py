"""Deterministic hybrid rank fusion for LangChain schema documents."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from langchain_core.documents import Document

from app.models.retrieval import RankedSchemaDocument, RetrievalSignal, RetrievedIndexDocument


def fuse_documents(
    vector_documents: Sequence[Document],
    keyword_documents: Sequence[Document],
    *,
    vector_weight: float,
    keyword_weight: float,
    rrf_constant: int,
) -> tuple[RankedSchemaDocument, ...]:
    """Fuse two bounded rank lists using LangChain's weighted RRF output order."""

    if vector_weight <= 0.0 or keyword_weight <= 0.0 or rrf_constant <= 0:
        raise ValueError("Hybrid ranking configuration is invalid.")
    rank_lists = [list(vector_documents), list(keyword_documents)]
    for documents in rank_lists:
        document_keys = [_document_key(document) for document in documents]
        if len(document_keys) != len(set(document_keys)):
            raise ValueError("Hybrid retrievers must return unique document keys per signal.")

    fused_documents = _fused_order(rank_lists, vector_weight, keyword_weight, rrf_constant)
    vector_hits = _signal_hits(vector_documents, "vector")
    keyword_hits = _signal_hits(keyword_documents, "keyword")
    results: list[RankedSchemaDocument] = []
    for document in fused_documents:
        key = _document_key(document)
        vector_hit = vector_hits.get(key)
        keyword_hit = keyword_hits.get(key)
        signals: list[RetrievalSignal] = []
        if vector_hit is not None:
            signals.append("vector")
        if keyword_hit is not None:
            signals.append("keyword")
        fused_score = sum(
            weight / (rank + rrf_constant)
            for weight, rank in (
                (vector_weight, vector_hit[0] if vector_hit else None),
                (keyword_weight, keyword_hit[0] if keyword_hit else None),
            )
            if rank is not None
        )
        results.append(
            RankedSchemaDocument(
                document=_retrieved_document(document),
                fused_score=fused_score,
                vector_rank=vector_hit[0] if vector_hit else None,
                keyword_rank=keyword_hit[0] if keyword_hit else None,
                vector_similarity=vector_hit[1] if vector_hit else None,
                keyword_score=keyword_hit[2] if keyword_hit else None,
                exact_identifier_match=bool(keyword_hit[3]) if keyword_hit else False,
                signals=tuple(signals),
            )
        )
    return tuple(results)


def _fused_order(
    rank_lists: list[list[Document]],
    vector_weight: float,
    keyword_weight: float,
    rrf_constant: int,
) -> list[Document]:
    """Use LangChain's built-in EnsembleRetriever weighted-rank implementation."""

    from langchain.retrievers import EnsembleRetriever

    combiner = EnsembleRetriever(
        retrievers=[],
        weights=[vector_weight, keyword_weight],
        c=rrf_constant,
        id_key="document_key",
    )
    return combiner.weighted_reciprocal_rank(rank_lists)


def _signal_hits(
    documents: Sequence[Document], signal: RetrievalSignal
) -> dict[str, tuple[int, float | None, float | None, bool]]:
    hits: dict[str, tuple[int, float | None, float | None, bool]] = {}
    for rank, document in enumerate(documents, start=1):
        metadata = document.metadata
        if metadata.get("retrieval_signal") != signal:
            raise ValueError("A hybrid document has incorrect signal metadata.")
        key = _document_key(document)
        vector_similarity = _optional_float(metadata.get("vector_similarity"))
        keyword_score = _optional_float(metadata.get("keyword_score"))
        hits[key] = (
            rank,
            vector_similarity,
            keyword_score,
            bool(metadata.get("exact_identifier_match")),
        )
    return hits


def _document_key(document: Document) -> str:
    key = document.metadata.get("document_key")
    if not isinstance(key, str) or not key:
        raise ValueError("A hybrid document is missing its stable document key.")
    return key


def _retrieved_document(document: Document) -> RetrievedIndexDocument:
    metadata = document.metadata
    category = metadata.get("category")
    if category not in {"table", "column", "relationship", "semantic_concept"}:
        raise ValueError("A hybrid document has an invalid category.")
    return RetrievedIndexDocument(
        document_key=_document_key(document),
        category=cast(Any, category),
        source_key=_required_string(metadata, "source_key"),
        schema_name=_required_string(metadata, "schema_name"),
        relation_name=_optional_string(metadata.get("relation_name")),
        column_name=_optional_string(metadata.get("column_name")),
        target_schema_name=_optional_string(metadata.get("target_schema_name")),
        target_relation_name=_optional_string(metadata.get("target_relation_name")),
        target_column_names=tuple(
            str(value) for value in (metadata.get("target_column_names") or [])
        ),
        qualified_identifier=_required_string(metadata, "qualified_identifier"),
        content=document.page_content,
        metadata={
            key: value
            for key, value in metadata.items()
            if key
            not in {
                "retrieval_signal",
                "retrieval_rank",
                "retrieval_raw_score",
                "vector_similarity",
                "keyword_score",
                "exact_identifier_match",
            }
        },
        source_fingerprint=_required_string(metadata, "source_fingerprint"),
        semantic_metadata_digest=_required_string(metadata, "semantic_metadata_digest"),
        document_version=_required_string(metadata, "document_version"),
        content_digest=_required_string(metadata, "content_digest"),
    )


def _required_string(metadata: dict[str, Any], name: str) -> str:
    value = metadata.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"A hybrid document is missing {name} metadata.")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
