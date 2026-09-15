"""Backend-owned LangChain chat-model construction."""

from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import Settings
from app.database.errors import ModelServiceError
from app.models.model_roles import ModelRole
from app.telemetry import emit_event

logger = logging.getLogger(__name__)


def create_chat_model(settings: Settings, role: ModelRole) -> Any:
    """Create an OpenRouter-compatible chat model without exposing credentials."""

    api_key = settings.openrouter_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise ModelServiceError("OPENROUTER_API_KEY is required for model operations.")
    try:
        model_name = settings.model_id_for(role)
    except ValueError as exc:
        raise ModelServiceError(str(exc)) from exc
    try:
        default_headers: dict[str, str] = {}
        if settings.openrouter_site_url:
            default_headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_site_name:
            default_headers["X-OpenRouter-Title"] = settings.openrouter_site_name
        model: Any = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=settings.openrouter_base_url,
            timeout=settings.model_request_timeout_seconds,
            max_retries=1,
            temperature=0,
            default_headers=default_headers or None,
        )
        emit_event(logger, "model_configured", model_role=role.value, model_id=model_name)
        return model
    except Exception as exc:
        raise ModelServiceError("The model integration could not be configured.") from exc
