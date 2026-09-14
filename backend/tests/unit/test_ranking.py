from __future__ import annotations

import pytest
from app.retrieval.ranking import fuse_documents
from langchain_core.documents import Document


def test_fuse_documents_merges_signals_by_stable_document_key() -> None:
    vector = [_document("a", "vector"), _document("b", "vector")]
    keyword = [_document("b", "keyword"), _document("a", "keyword")]

    result = fuse_documents(
        vector,
        keyword,
        vector_weight=0.6,
        keyword_weight=0.4,
        rrf_constant=60,
    )

    assert [item.document.document_key for item in result] == ["a", "b"]
    assert result[0].signals == ("vector", "keyword")
    assert result[0].vector_rank == 1
    assert result[0].keyword_rank == 2
    assert result[0].fused_score > result[1].fused_score


def test_fuse_documents_rejects_duplicates_within_one_signal() -> None:
    duplicate = _document("a", "vector")

    with pytest.raises(ValueError, match="unique document keys"):
        fuse_documents(
            [duplicate, duplicate],
            [],
            vector_weight=0.6,
            keyword_weight=0.4,
            rrf_constant=60,
        )


def _document(document_key: str, signal: str) -> Document:
    return Document(
        id=document_key,
        page_content=f"Document {document_key}",
        metadata={
            "document_key": document_key,
            "retrieval_signal": signal,
            "category": "table",
            "source_key": "source",
            "schema_name": "analytics",
            "relation_name": document_key,
            "qualified_identifier": f'"analytics"."{document_key}"',
            "source_fingerprint": "sha256:test",
            "semantic_metadata_digest": "sha256:metadata",
            "document_version": "schema-document-v1",
            "content_digest": f"sha256:{document_key}",
        },
    )
