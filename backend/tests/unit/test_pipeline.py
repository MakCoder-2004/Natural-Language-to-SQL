"""Unit tests for basic pipeline orchestration and validation gates."""

from typing import Any

import pytest
from app.config import Settings
from app.database.errors import QueryValidationError
from app.database.models import (
    DatabaseIdentity,
    RelationMetadata,
    SchemaMetadata,
    SourceSchemaSnapshot,
)
from app.database.services import DatabaseServices
from app.database.source_connection import SourceDatabase
from app.models.results import GroundedAnswer, QueryResult
from app.models.retrieval import RetrievalDiagnostics, RetrievalLimits, RetrievalResult
from app.models.sql import SqlProposal, SqlValidationResult, sql_hash
from app.services.pipeline import BasicSqlPipelineService
from sqlalchemy import create_engine


def _settings() -> Settings:
    return Settings(max_question_length=20, _env_file=None)  # type: ignore[call-arg]


def _retrieval() -> RetrievalResult:
    limits = RetrievalLimits(1, 1, 1, 1, 1, 1, 1, 1, 100, 0.2, 0.6, 0.4, 60)
    diagnostics = RetrievalDiagnostics(0, 0, 0, 0, 0, 0, 0, {}, limits)
    return RetrievalResult((), (), (), (), "context", "fingerprint", diagnostics)


def _snapshot() -> SourceSchemaSnapshot:
    return SourceSchemaSnapshot(
        DatabaseIdentity("source", "readonly"),
        ("main",),
        (SchemaMetadata("main", (RelationMetadata("main", "values_table", "table", ()),)),),
        "fingerprint",
    )


class _Retrieval:
    def retrieve(self, question: str) -> RetrievalResult:
        return _retrieval()


class _Generation:
    def generate(self, question: str, retrieval: RetrievalResult) -> SqlProposal:
        return SqlProposal.create(sql="SELECT 1", interpretation="Returns one.")


class _Validation:
    def validate(self, sql: str, snapshot: SourceSchemaSnapshot) -> SqlValidationResult:
        return SqlValidationResult(True, sql, sql_hash(sql), (), (), (), (), (), (), True, True)


class _Executor:
    def execute(self, binding: Any, validation: SqlValidationResult) -> QueryResult:
        return QueryResult(("value",), ((1,),), 1, 1, False, 1, (), validation.sql_hash)


class _Answer:
    def generate(self, question: str, sql: str, result: Any) -> GroundedAnswer:
        return GroundedAnswer("One.", (), "The query returned one row.")


def test_pipeline_requires_validation_before_execution() -> None:
    engine = create_engine("sqlite://")
    services = DatabaseServices(SourceDatabase(engine, ("main",)), None)
    pipeline = BasicSqlPipelineService(
        _settings(),
        services,
        retrieval_service=_Retrieval(),
        sql_generation_service=_Generation(),
        validation_service=type(
            "RejectingValidation",
            (),
            {
                "validate": lambda self, sql, snapshot: SqlValidationResult.rejected(
                    sql, errors=("unsafe",)
                )
            },
        )(),
        executor=_Executor(),
        answer_service=_Answer(),
        snapshot_provider=lambda _: _snapshot(),
    )

    with pytest.raises(QueryValidationError, match="unsafe"):
        pipeline.run("count values")


def test_pipeline_returns_complete_result_after_validation() -> None:
    engine = create_engine("sqlite://")
    services = DatabaseServices(SourceDatabase(engine, ("main",)), None)
    pipeline = BasicSqlPipelineService(
        _settings(),
        services,
        retrieval_service=_Retrieval(),
        sql_generation_service=_Generation(),
        validation_service=_Validation(),
        executor=_Executor(),
        answer_service=_Answer(),
        snapshot_provider=lambda _: _snapshot(),
    )

    result = pipeline.run("count values")

    assert result.validation.passed
    assert result.result.row_count == 1
    assert result.answer.answer == "One."
