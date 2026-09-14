"""LangChain retriever adapters for the local schema index."""

from __future__ import annotations

from typing import Any

from langchain.retrievers import EnsembleRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from app.database.errors import EmbeddingServiceError
from app.models.retrieval import IndexSearchHit, RetrievedIndexDocument


class VectorSchemaRetriever(BaseRetriever):
    """Expose bounded pgvector search through LangChain's retriever contract."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    repository: Any = Field(exclude=True)
    # Protocols are not runtime-checkable, so Pydantic cannot validate this excluded field.
    embedding_provider: Any = Field(exclude=True)
    source_key: str
    source_fingerprint: str
    embedding_model: str
    embedding_dimension: int
    limit: int
    minimum_similarity: float

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        del run_manager
        query_vector = self.embedding_provider.embed_query(query)
        if len(query_vector) != self.embedding_dimension:
            raise EmbeddingServiceError("The query embedding dimension does not match the index.")
        hits = self.repository.search_vector_documents(
            self.source_key,
            self.source_fingerprint,
            query_vector,
            embedding_model=self.embedding_model,
            minimum_similarity=self.minimum_similarity,
            limit=self.limit,
        )
        return [_document_from_hit(hit) for hit in hits]


class KeywordSchemaRetriever(BaseRetriever):
    """Expose bounded PostgreSQL keyword and metadata search as a retriever."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    repository: Any = Field(exclude=True)
    source_key: str
    source_fingerprint: str
    limit: int

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        del run_manager
        hits = self.repository.search_keyword_documents(
            self.source_key,
            self.source_fingerprint,
            query,
            limit=self.limit,
        )
        return [_document_from_hit(hit) for hit in hits]


def create_ensemble_retriever(
    vector_retriever: VectorSchemaRetriever,
    keyword_retriever: KeywordSchemaRetriever,
    *,
    vector_weight: float,
    keyword_weight: float,
    rrf_constant: int,
) -> EnsembleRetriever:
    """Create LangChain's deterministic weighted reciprocal-rank combiner."""

    return EnsembleRetriever(
        retrievers=[vector_retriever, keyword_retriever],
        weights=[vector_weight, keyword_weight],
        c=rrf_constant,
        id_key="document_key",
    )


def _document_from_hit(hit: IndexSearchHit) -> Document:
    return document_from_indexed_document(
        hit.document,
        {
            "retrieval_signal": hit.signal,
            "retrieval_rank": hit.rank,
            "retrieval_raw_score": hit.raw_score,
            "vector_similarity": hit.vector_similarity,
            "keyword_score": hit.keyword_score,
            "exact_identifier_match": hit.exact_identifier_match,
        },
    )


def document_from_indexed_document(
    document: RetrievedIndexDocument,
    extra_metadata: dict[str, Any] | None = None,
) -> Document:
    """Convert an indexed domain document to a LangChain document."""

    metadata: dict[str, Any] = {
        **document.metadata,
        "document_key": document.document_key,
        "category": document.category,
        "source_key": document.source_key,
        "schema_name": document.schema_name,
        "relation_name": document.relation_name,
        "column_name": document.column_name,
        "target_schema_name": document.target_schema_name,
        "target_relation_name": document.target_relation_name,
        "target_column_names": list(document.target_column_names),
        "qualified_identifier": document.qualified_identifier,
        "source_fingerprint": document.source_fingerprint,
        "document_version": document.document_version,
        "content_digest": document.content_digest,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return Document(
        id=document.document_key,
        page_content=document.content,
        metadata=metadata,
    )
