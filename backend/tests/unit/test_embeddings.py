from typing import Any

import httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch
from app.config import Settings
from app.database.errors import EmbeddingServiceError
from app.retrieval.embeddings import OpenRouterEmbeddingProvider, create_embedding_provider
from pydantic import SecretStr


class FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.request: httpx.Request | None = None

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.request = httpx.Request("POST", url, json=kwargs["json"])
        return self.response


def test_openrouter_embedding_provider_batches_and_orders_vectors(
    monkeypatch: MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        json={
            "data": [
                {"index": 1, "embedding": [0, 1]},
                {"index": 0, "embedding": [1, 0]},
            ]
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/embeddings"),
    )
    fake_client = FakeClient(response)
    monkeypatch.setattr("app.retrieval.embeddings.httpx.Client", lambda **_kwargs: fake_client)
    provider = OpenRouterEmbeddingProvider(
        SecretStr("test-key"), "https://openrouter.ai/api/v1", "test-embedding", 10
    )

    vectors = provider.embed_documents(("first", "second"))

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert fake_client.request is not None
    assert fake_client.request.url == "https://openrouter.ai/api/v1/embeddings"
    assert fake_client.request.content == b'{"model":"test-embedding","input":["first","second"]}'


@pytest.mark.parametrize(
    "payload",
    [
        {"data": []},
        {"data": [{"index": 0, "embedding": []}]},
        {"data": [{"index": 0, "embedding": [1]}, {"index": 1, "embedding": [1, 2]}]},
    ],
)
def test_openrouter_embedding_provider_rejects_invalid_vectors(
    monkeypatch: MonkeyPatch, payload: object
) -> None:
    response = httpx.Response(
        200,
        json=payload,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/embeddings"),
    )
    monkeypatch.setattr(
        "app.retrieval.embeddings.httpx.Client", lambda **_kwargs: FakeClient(response)
    )
    provider = OpenRouterEmbeddingProvider(
        SecretStr("test-key"), "https://openrouter.ai/api/v1", "test-embedding", 10
    )

    with pytest.raises(EmbeddingServiceError):
        provider.embed_documents(("one",))


def test_create_embedding_provider_requires_backend_credentials() -> None:
    settings_constructor: Any = Settings
    settings = settings_constructor(_env_file=None, openrouter_api_key=None, embedding_model=None)

    with pytest.raises(EmbeddingServiceError):
        create_embedding_provider(settings)
