"""Unit tests for Milestone 5 pipeline contracts."""

from app.models.query import QueryRequest
from app.models.results import QueryResult
from app.models.sql import SqlProposal, sql_hash


def test_query_request_generates_distinct_backend_identifiers() -> None:
    first = QueryRequest.create("show totals")
    second = QueryRequest.create("show totals")

    assert first.question == second.question
    assert first.query_id != second.query_id
    assert first.pipeline_run_id != second.pipeline_run_id


def test_sql_proposal_hashes_exact_sql() -> None:
    proposal = SqlProposal.create(sql="SELECT 1", interpretation="One", tables_used=())

    assert proposal.sql_hash == sql_hash("SELECT 1")
    assert proposal.sql_hash != sql_hash("SELECT  1")


def test_empty_result_is_distinct_from_failure() -> None:
    result = QueryResult(
        columns=("total",),
        rows=(),
        row_count=0,
        returned_row_count=0,
        truncated=False,
        result_bytes=2,
        warnings=(),
        executed_sql_hash="hash",
    )

    assert result.is_empty
    assert result.rows == ()
