from app.api.errors import error_response
from app.database.errors import EmbeddingServiceError


def test_embedding_failure_explains_required_configuration_without_provider_details() -> None:
    response = error_response(EmbeddingServiceError("provider response contained a secret"))

    assert response.status_code == 503
    assert response.body == (
        b'{"error":{"code":"embedding_error","message":"Schema indexing requires a '
        b'configured OpenRouter embedding model.","details":{}}}'
    )
