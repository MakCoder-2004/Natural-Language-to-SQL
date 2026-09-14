from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from app.models.retrieval import IndexSearchHit, RetrievedIndexDocument
from app.retrieval.retrievers import (
    KeywordSchemaRetriever,
    VectorSchemaRetriever,
    create_ensemble_retriever,
)


class FakeEmbeddingProvider:
    model_id = "test-embedding"

    def embed_documents(self, _texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return ()

    def embed_query(self, _text: str) -> tuple[float, ...]:
        return (1.0, 0.0)


class FakeRepository:
    def __init__(self, documents: tuple[RetrievedIndexDocument, ...]) -> None:
        self.documents = documents
        self.vector_queries: list[tuple[float, ...]] = []
        self.keyword_queries: list[str] = []

    def search_vector_documents(
        self,
        _source_key: str,
        _source_fingerprint: str,
        query_vector: tuple[float, ...],
        *,
        embedding_model: str,
        minimum_similarity: float,
        limit: int,
    ) -> tuple[IndexSearchHit, ...]:
        assert embedding_model == "test-embedding"
        assert minimum_similarity == 0.2
        self.vector_queries.append(query_vector)
        return tuple(
            IndexSearchHit(document, "vector", rank, 0.9, vector_similarity=0.9)
            for rank, document in enumerate(self.documents[:limit], start=1)
        )

    def search_keyword_documents(
        self,
        _source_key: str,
        _source_fingerprint: str,
        question: str,
        *,
        limit: int,
    ) -> tuple[IndexSearchHit, ...]:
        self.keyword_queries.append(question)
        return tuple(
            IndexSearchHit(document, "keyword", rank, 1.0, keyword_score=1.0)
            for rank, document in enumerate(reversed(self.documents[:limit]), start=1)
        )


def test_langchain_retrievers_return_documents_and_preserve_signal_metadata() -> None:
    documents = _documents()
    repository = FakeRepository(documents)
    vector = VectorSchemaRetriever(
        repository=cast(Any, repository),
        embedding_provider=FakeEmbeddingProvider(),
        source_key="source",
        source_fingerprint="sha256:test",
        embedding_model="test-embedding",
        embedding_dimension=2,
        limit=2,
        minimum_similarity=0.2,
    )
    keyword = KeywordSchemaRetriever(
        repository=cast(Any, repository),
        source_key="source",
        source_fingerprint="sha256:test",
        limit=2,
    )

    vector_documents = vector.invoke("find accounts")
    keyword_documents = keyword.invoke("find accounts")

    assert [document.metadata["retrieval_signal"] for document in vector_documents] == [
        "vector",
        "vector",
    ]
    assert keyword_documents[0].metadata["retrieval_signal"] == "keyword"
    assert vector_documents[0].metadata["document_key"] == documents[0].document_key
    assert repository.vector_queries == [(1.0, 0.0)]
    assert repository.keyword_queries == ["find accounts"]


def test_langchain_ensemble_retriever_fuses_by_document_key() -> None:
    documents = _documents()
    repository = FakeRepository(documents)
    vector = VectorSchemaRetriever(
        repository=cast(Any, repository),
        embedding_provider=FakeEmbeddingProvider(),
        source_key="source",
        source_fingerprint="sha256:test",
        embedding_model="test-embedding",
        embedding_dimension=2,
        limit=2,
        minimum_similarity=0.2,
    )
    keyword = KeywordSchemaRetriever(
        repository=cast(Any, repository),
        source_key="source",
        source_fingerprint="sha256:test",
        limit=2,
    )
    ensemble = create_ensemble_retriever(
        vector,
        keyword,
        vector_weight=0.6,
        keyword_weight=0.4,
        rrf_constant=60,
    )

    result = ensemble.invoke("find accounts")

    assert len(result) == 2
    assert {document.metadata["document_key"] for document in result} == {
        document.document_key for document in documents
    }


def _documents() -> tuple[RetrievedIndexDocument, ...]:
    return tuple(
        RetrievedIndexDocument(
            document_key=f"table:{index}",
            category="table",
            source_key="source",
            schema_name="analytics",
            relation_name=f"table_{index}",
            column_name=None,
            target_schema_name=None,
            target_relation_name=None,
            target_column_names=(),
            qualified_identifier=f'"analytics"."table_{index}"',
            content=f"Table {index}",
            metadata={},
            source_fingerprint="sha256:test",
            semantic_metadata_digest="sha256:metadata",
            document_version="schema-document-v1",
            content_digest=f"sha256:content-{index}",
        )
        for index in range(2)
    )
