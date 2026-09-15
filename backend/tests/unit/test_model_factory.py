from typing import Any

from app.chains.model_factory import create_chat_model
from app.config import Settings
from app.models.model_roles import ModelRole
from pydantic import SecretStr


def test_chat_factory_resolves_model_id_from_role(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.chains.model_factory.ChatOpenAI", FakeChatOpenAI)
    settings_constructor: Any = Settings
    settings = settings_constructor(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        sql_model="provider/sql-model",
    )

    model = create_chat_model(settings, ModelRole.SQL_GENERATION)

    assert captured["model"] == "provider/sql-model"
    assert isinstance(model, FakeChatOpenAI)


def test_chat_factory_allows_roles_to_share_a_model(monkeypatch: Any) -> None:
    captured: list[str] = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.append(kwargs["model"])

    monkeypatch.setattr("app.chains.model_factory.ChatOpenAI", FakeChatOpenAI)
    settings_constructor: Any = Settings
    settings = settings_constructor(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        question_model="provider/shared",
        answer_model="provider/shared",
    )

    create_chat_model(settings, ModelRole.QUESTION_ANALYSIS)
    create_chat_model(settings, ModelRole.ANSWER_GENERATION)

    assert captured == ["provider/shared", "provider/shared"]
