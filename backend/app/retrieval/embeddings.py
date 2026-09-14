"""OpenRouter embedding provider with a provider-neutral LangChain interface."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

from app.config import Settings
from app.database.errors import EmbeddingServiceError


class EmbeddingProvider(Protocol):
    """Minimal provider contract required by the indexing service."""

    @property
    def model_id(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


class OpenRouterEmbeddingProvider:
    """Call OpenRouter's OpenAI-compatible embeddings endpoint."""

    def __init__(
        self,
        api_key: SecretStr,
        base_url: str,
        model: str,
        timeout_seconds: int,
    ) -> None:
        if not api_key.get_secret_value().strip() or not model.strip():
            raise EmbeddingServiceError("Embedding model configuration is incomplete.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_id = model
        self._timeout_seconds = timeout_seconds

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json={"model": self._model_id, "input": list(texts)},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise EmbeddingServiceError("The embedding service request failed.") from exc
        return _parse_embeddings(payload, len(texts))


def create_embedding_provider(settings: Settings) -> OpenRouterEmbeddingProvider:
    """Create the configured OpenRouter embedding provider."""

    if (
        settings.openrouter_api_key is None
        or not settings.openrouter_api_key.get_secret_value().strip()
    ):
        raise EmbeddingServiceError("OPENROUTER_API_KEY is required for indexing.")
    if settings.embedding_model is None or not settings.embedding_model.strip():
        raise EmbeddingServiceError("EMBEDDING_MODEL is required for indexing.")
    return OpenRouterEmbeddingProvider(
        settings.openrouter_api_key,
        settings.openrouter_base_url,
        settings.embedding_model,
        settings.embedding_request_timeout_seconds,
    )


def _parse_embeddings(payload: Any, expected_count: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise EmbeddingServiceError("The embedding service returned an invalid response.")
    rows = payload["data"]
    if len(rows) != expected_count:
        raise EmbeddingServiceError("The embedding service returned an unexpected vector count.")
    indexed_vectors: list[tuple[int, tuple[float, ...]]] = []
    for fallback_index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("embedding"), list):
            raise EmbeddingServiceError("The embedding service returned an invalid vector.")
        raw_vector = row["embedding"]
        vector: list[float] = []
        for value in raw_vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EmbeddingServiceError("The embedding service returned an invalid vector.")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise EmbeddingServiceError("The embedding service returned an invalid vector.")
            vector.append(numeric_value)
        if not vector:
            raise EmbeddingServiceError("The embedding service returned an empty vector.")
        raw_index = row.get("index", fallback_index)
        if not isinstance(raw_index, int):
            raise EmbeddingServiceError("The embedding service returned invalid vector ordering.")
        indexed_vectors.append((raw_index, tuple(vector)))
    indexed_vectors.sort(key=lambda item: item[0])
    if [index for index, _ in indexed_vectors] != list(range(expected_count)):
        raise EmbeddingServiceError("The embedding service returned invalid vector ordering.")
    dimensions = {len(vector) for _, vector in indexed_vectors}
    if len(dimensions) != 1:
        raise EmbeddingServiceError("The embedding service returned mixed vector dimensions.")
    return tuple(vector for _, vector in indexed_vectors)
