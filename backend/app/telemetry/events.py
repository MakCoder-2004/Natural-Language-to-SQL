"""Structured log events with a conservative sensitive-field boundary."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_NAMES = frozenset(
    {
        "api_key",
        "authorization",
        "connection_url",
        "database_url",
        "password",
        "prompt",
        "rows",
        "result_rows",
        "sql",
    }
)


def emit_event(logger: logging.Logger, event_name: str, **fields: Any) -> None:
    """Write one JSON event after removing fields unsafe for normal telemetry."""

    payload: dict[str, Any] = {
        "event_name": event_name,
        "event_version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    payload.update(
        {key: value for key, value in fields.items() if key.lower() not in _SENSITIVE_NAMES}
    )
    logger.info(json.dumps(payload, default=str, sort_keys=True))
