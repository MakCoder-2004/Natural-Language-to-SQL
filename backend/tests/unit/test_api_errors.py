from app.api.errors import error_response
from app.database.errors import EmbeddingServiceError


def test_embedding_failure_explains_safe_provider_action() -> None:
    response = error_response(EmbeddingServiceError("provider response contained a secret"))

    assert response.status_code == 503
    assert response.body == (
        b'{"error":{"code":"embedding_error","message":"The OpenRouter embedding request '
        b'failed. Check the API key, credits, and rate limits.","details":{}}}'
    )
