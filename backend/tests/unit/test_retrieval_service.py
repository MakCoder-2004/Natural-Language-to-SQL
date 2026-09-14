from typing import Any, cast

import pytest
from app.config import Settings
from app.database.errors import IndexReadinessError, NoRelevantSchemaError
from app.database.services import DatabaseServices
from app.services.retrieval import HybridSchemaRetrievalService


def test_retrieval_fails_closed_when_database_dependencies_are_missing() -> None:
    settings_constructor: Any = Settings
    settings = cast(Settings, settings_constructor(_env_file=None))
    service = HybridSchemaRetrievalService(settings, DatabaseServices())

    with pytest.raises(IndexReadinessError) as raised:
        service.retrieve("find accounts")

    assert raised.value.reason == "index_unavailable"


def test_retrieval_rejects_empty_questions_before_database_work() -> None:
    settings_constructor: Any = Settings
    settings = cast(Settings, settings_constructor(_env_file=None))
    service = HybridSchemaRetrievalService(settings, None)

    with pytest.raises(NoRelevantSchemaError):
        service.retrieve("   ")
