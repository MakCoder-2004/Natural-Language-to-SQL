"""Provider-neutral embedding service built on LangChain integrations."""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from app.config import Settings
from app.database.errors import EmbeddingServiceError
from app.models.model_roles import ModelRole
from app.telemetry import emit_event

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Minimal provider contract required by indexing and retrieval."""

    @property
    def model_id(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...

    def embed_query(self, text: str) -> tuple[float, ...]: ...


class LangChainEmbeddingProvider:
    """Adapt a LangChain embedding integration to the indexing contract."""

    def __init__(self, embedder: Any, model_id: str) -> None:
        self._embedder = embedder
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        try:
            raw_vectors = self._embedder.embed_documents(list(texts))
        except Exception as exc:
            raise EmbeddingServiceError("The embedding service request failed.") from exc
        return _validate_vectors(raw_vectors, len(texts))

    def embed_query(self, text: str) -> tuple[float, ...]:
        """Embed one question with the same model used for indexing."""

        if not text.strip():
            raise EmbeddingServiceError("The query to embed must not be empty.")
        try:
            raw_vector = self._embedder.embed_query(text)
        except Exception as exc:
            raise EmbeddingServiceError("The embedding service request failed.") from exc
        return _validate_vectors([raw_vector], 1)[0]


def create_embedding_provider(settings: Settings) -> LangChainEmbeddingProvider:
    """Create the configured LangChain embedding integration."""

    model = settings.embedding_model
    if model is None or not model.strip():
        raise EmbeddingServiceError("EMBEDDING_MODEL is required for indexing.")
    try:
        if settings.embedding_provider == "ollama":
            embedder: Any = OllamaEmbeddings(
                model=model,
                base_url=settings.ollama_base_url,
                client_kwargs={"timeout": settings.embedding_request_timeout_seconds},
            )
            emit_event(
                logger,
                "model_configured",
                model_role=ModelRole.EMBEDDING.value,
                model_provider="ollama",
                model_id=model,
            )
            return LangChainEmbeddingProvider(embedder, model)

        api_key = settings.openrouter_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise EmbeddingServiceError("OPENROUTER_API_KEY is required for indexing.")
        default_headers: dict[str, str] = {}
        if settings.openrouter_site_url:
            default_headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_site_name:
            default_headers["X-OpenRouter-Title"] = settings.openrouter_site_name
        embedder = OpenAIEmbeddings(
            model=model,
            api_key=api_key,
            base_url=settings.openrouter_base_url,
            chunk_size=settings.embedding_batch_size,
            timeout=settings.embedding_request_timeout_seconds,
            max_retries=1,
            tiktoken_enabled=False,
            check_embedding_ctx_length=False,
            default_headers=default_headers or None,
            model_kwargs={"encoding_format": "float"},
        )
    except Exception as exc:
        raise EmbeddingServiceError("The embedding integration could not be configured.") from exc
    emit_event(logger, "model_configured", model_role=ModelRole.EMBEDDING.value, model_id=model)
    return LangChainEmbeddingProvider(embedder, model)


def _validate_vectors(raw_vectors: Any, expected_count: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(raw_vectors, list) or len(raw_vectors) != expected_count:
        raise EmbeddingServiceError("The embedding service returned an unexpected vector count.")
    vectors: list[tuple[float, ...]] = []
    for raw_vector in raw_vectors:
        if not isinstance(raw_vector, list) or not raw_vector:
            raise EmbeddingServiceError("The embedding service returned an invalid vector.")
        vector: list[float] = []
        for value in raw_vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EmbeddingServiceError("The embedding service returned an invalid vector.")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise EmbeddingServiceError("The embedding service returned an invalid vector.")
            vector.append(numeric_value)
        vectors.append(tuple(vector))
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise EmbeddingServiceError("The embedding service returned mixed vector dimensions.")
    return tuple(vectors)
