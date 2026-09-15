import json
import logging

from _pytest.logging import LogCaptureFixture
from app.telemetry.events import emit_event


def test_telemetry_emits_json_and_filters_sensitive_fields(caplog: LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        emit_event(
            logging.getLogger("test.telemetry"),
            "query_completed",
            query_id="query-1",
            sql="SELECT secret FROM users",
            password="hidden",
            row_count=2,
        )

    record = caplog.records[-1]
    payload = json.loads(record.message)
    assert payload["event_name"] == "query_completed"
    assert payload["query_id"] == "query-1"
    assert payload["row_count"] == 2
    assert "sql" not in payload
    assert "password" not in payload
