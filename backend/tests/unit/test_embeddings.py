from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from app.config import Settings
from app.database.errors import EmbeddingServiceError
from app.retrieval.embeddings import LangChainEmbeddingProvider, create_embedding_provider
from pydantic import SecretStr


class FakeEmbedder:
    def __init__(self, vectors: object) -> None:
        self.vectors = vectors
        self.texts: list[str] | None = None

    def embed_documents(self, texts: list[str]) -> object:
        self.texts = texts
        return self.vectors


def test_langchain_embedding_provider_batches_texts_and_validates_vectors() -> None:
    embedder = FakeEmbedder([[1, 0], [0, 1]])
    provider = LangChainEmbeddingProvider(embedder, "test-embedding")

    vectors = provider.embed_documents(("first", "second"))

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert embedder.texts == ["first", "second"]
    assert provider.model_id == "test-embedding"


@pytest.mark.parametrize(
    "vectors",
    [
        [],
        [[]],
        [[1], [1, 2]],
        [[True]],
        [[float("inf")]],
    ],
)
def test_langchain_embedding_provider_rejects_invalid_vectors(vectors: object) -> None:
    provider = LangChainEmbeddingProvider(FakeEmbedder(vectors), "test-embedding")

    with pytest.raises(EmbeddingServiceError):
        provider.embed_documents(("one",))


def test_langchain_embedding_provider_translates_provider_failures() -> None:
    class FailingEmbedder:
        def embed_documents(self, _texts: list[str]) -> object:
            raise RuntimeError("provider failure")

    provider = LangChainEmbeddingProvider(FailingEmbedder(), "test-embedding")

    with pytest.raises(EmbeddingServiceError, match="request failed"):
        provider.embed_documents(("one",))


def test_create_embedding_provider_uses_openrouter_with_langchain(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.retrieval.embeddings.OpenAIEmbeddings", FakeOpenAIEmbeddings)
    settings_constructor: Any = Settings
    settings = settings_constructor(
        _env_file=None,
        source_database_url=SecretStr("postgresql+psycopg://source:password@source/db"),
        index_database_url=SecretStr("postgresql+psycopg://index:password@index/db"),
        openrouter_api_key=SecretStr("test-key"),
        embedding_model="provider/embedding-model",
    )

    provider = create_embedding_provider(settings)

    assert provider.model_id == "provider/embedding-model"
    assert captured["model"] == "provider/embedding-model"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["api_key"] == SecretStr("test-key")
    assert captured["tiktoken_enabled"] is False
    assert captured["model_kwargs"] == {"encoding_format": "float"}


def test_create_embedding_provider_requires_backend_credentials() -> None:
    settings_constructor: Any = Settings
    settings = settings_constructor(_env_file=None, openrouter_api_key=None, embedding_model=None)

    with pytest.raises(EmbeddingServiceError):
        create_embedding_provider(settings)
