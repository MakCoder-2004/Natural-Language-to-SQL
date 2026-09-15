"""Backend-owned LangChain chat-model construction."""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from app.config import Settings
from app.database.errors import ModelServiceError


def create_chat_model(settings: Settings, model_name: str | None) -> Any:
    """Create an OpenRouter-compatible chat model without exposing credentials."""

    api_key = settings.openrouter_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise ModelServiceError("OPENROUTER_API_KEY is required for model operations.")
    if model_name is None or not model_name.strip():
        raise ModelServiceError("The requested model role is not configured.")
    try:
        default_headers: dict[str, str] = {}
        if settings.openrouter_site_url:
            default_headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_site_name:
            default_headers["X-OpenRouter-Title"] = settings.openrouter_site_name
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=settings.openrouter_base_url,
            timeout=settings.model_request_timeout_seconds,
            max_retries=2,
            temperature=0,
            default_headers=default_headers or None,
        )
    except Exception as exc:
        raise ModelServiceError("The model integration could not be configured.") from exc
