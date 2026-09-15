"""Unit tests for structured SQL and answer model boundaries."""

import json
from typing import Any, cast

from app.chains.answer_generation import GroundedAnswerOutput, build_answer_generation_chain
from app.chains.sql_generation import SqlProposalOutput, build_sql_generation_chain
from app.config import Settings
from app.models.results import QueryResult
from app.models.retrieval import RetrievalDiagnostics, RetrievalLimits, RetrievalResult
from app.services.answer_generation import AnswerGenerationService
from app.services.sql_correction import SqlCorrectionService
from app.services.sql_generation import SqlGenerationService
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


def _settings() -> Settings:
    settings_constructor: Any = Settings
    return cast(Settings, settings_constructor(_env_file=None))


def _retrieval() -> RetrievalResult:
    limits = RetrievalLimits(
        vector_candidate_limit=1,
        keyword_candidate_limit=1,
        max_selected_tables=1,
        max_columns_per_table=1,
        max_relationships=1,
        max_relationship_hops=1,
        max_expanded_tables=1,
        max_context_documents=1,
        max_context_characters=100,
        min_vector_similarity=0.2,
        vector_weight=0.6,
        keyword_weight=0.4,
        rrf_constant=60,
    )
    return RetrievalResult(
        documents=(),
        tables=(),
        columns=(),
        relationships=(),
        context_text='TABLE "analytics"."events" ("occurred_at" timestamp)',
        index_fingerprint="fingerprint",
        diagnostics=RetrievalDiagnostics(0, 0, 0, 0, 0, 0, 0, {}, limits),
    )


def test_sql_generation_converts_structured_output_to_proposal() -> None:
    chain = RunnableLambda(
        lambda _: SqlProposalOutput(
            sql="SELECT count(*) FROM analytics.events",
            interpretation="Counts events.",
            tables_used=["analytics.events"],
        )
    )

    proposal = SqlGenerationService(_settings(), chain=chain).generate("count events", _retrieval())

    assert proposal.sql == "SELECT count(*) FROM analytics.events"
    assert proposal.tables_used == ("analytics.events",)


def test_sql_correction_uses_a_separate_injected_chain() -> None:
    chain = RunnableLambda(
        lambda values: SqlProposalOutput(
            sql="SELECT count(*) FROM analytics.events",
            interpretation="Corrected count.",
            tables_used=["analytics.events"],
        )
    )

    proposal = SqlCorrectionService(_settings(), chain=chain).correct(
        "count events", _retrieval(), "SELECT count(*) FROM events", ("missing relation",)
    )

    assert proposal.sql == "SELECT count(*) FROM analytics.events"
    assert proposal.interpretation == "Corrected count."


def test_answer_generation_converts_structured_output() -> None:
    chain = RunnableLambda(
        lambda _: GroundedAnswerOutput(
            answer="There are 3 events.",
            evidence_summary="The executed query returned one count row.",
        )
    )
    result = QueryResult(
        columns=("count",),
        rows=((3,),),
        row_count=1,
        returned_row_count=1,
        truncated=False,
        result_bytes=1,
        warnings=(),
        executed_sql_hash="hash",
    )

    answer = AnswerGenerationService(_settings(), chain=chain).generate(
        "count events", "SELECT count(*) FROM analytics.events", result
    )

    assert answer.answer == "There are 3 events."
    assert answer.evidence_summary.startswith("The executed")


def test_sql_lcel_chain_parses_model_message() -> None:
    model = RunnableLambda(
        lambda _: AIMessage(
            content=json.dumps(
                {
                    "sql": "SELECT 1",
                    "interpretation": "Returns one.",
                    "tables_used": [],
                    "assumptions": [],
                    "warnings": [],
                }
            )
        )
    )

    output = build_sql_generation_chain(model).invoke(
        {"question": "return one", "schema_context": "No tables required."}
    )

    assert isinstance(output, SqlProposalOutput)
    assert output.sql == "SELECT 1"


def test_answer_lcel_chain_parses_model_message() -> None:
    model = RunnableLambda(
        lambda _: AIMessage(
            content=json.dumps(
                {
                    "answer": "There are no rows.",
                    "caveats": [],
                    "evidence_summary": "The result was empty.",
                }
            )
        )
    )

    output = build_answer_generation_chain(model).invoke(
        {"question": "show events", "sql": "SELECT 1", "result_json": '{"rows": []}'}
    )

    assert isinstance(output, GroundedAnswerOutput)
    assert output.answer == "There are no rows."
