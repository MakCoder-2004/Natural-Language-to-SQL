"""Basic question-to-result SQL pipeline orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from app.config import Settings
from app.database.errors import (
    DatabaseUnavailableError,
    QueryValidationError,
)
from app.database.models import SourceSchemaSnapshot
from app.database.services import DatabaseServices
from app.database.source_execution import SourceExecutionBinding
from app.database.source_introspection import SourceIntrospector
from app.database.source_query import ReadonlySqlExecutor
from app.models.pipeline import PipelineResult
from app.models.query import QueryRequest
from app.models.retrieval import RetrievalResult
from app.models.sql import SqlValidationResult
from app.services.answer_generation import AnswerGenerationService
from app.services.retrieval import HybridSchemaRetrievalService
from app.services.sql_generation import SqlGenerationService
from app.services.visualization import VisualizationSelector
from app.validation.sql import SqlValidationService

logger = logging.getLogger(__name__)


class BasicSqlPipelineService:
    """Run a clear question through retrieval, validation, execution, and answer stages."""

    def __init__(
        self,
        settings: Settings,
        database_services: DatabaseServices | None,
        *,
        retrieval_service: Any | None = None,
        sql_generation_service: Any | None = None,
        validation_service: Any | None = None,
        executor: Any | None = None,
        answer_service: Any | None = None,
        visualization_selector: VisualizationSelector | None = None,
        snapshot_provider: Callable[[Any], SourceSchemaSnapshot] | None = None,
    ) -> None:
        self.settings = settings
        self.database_services = database_services
        self.retrieval_service = retrieval_service or HybridSchemaRetrievalService(
            settings, database_services
        )
        self.sql_generation_service = sql_generation_service or SqlGenerationService(settings)
        self.validation_service = validation_service or SqlValidationService()
        self.executor = executor or ReadonlySqlExecutor(settings)
        self.answer_service = answer_service or AnswerGenerationService(settings)
        self.visualization_selector = visualization_selector or VisualizationSelector()
        self.snapshot_provider = snapshot_provider or (
            lambda database: SourceIntrospector(database).introspect()
        )

    def run(self, question: str) -> PipelineResult:
        """Execute one clear-question vertical slice with backend-owned controls."""

        request = self._request(question)
        if self.database_services is None or self.database_services.source is None:
            raise DatabaseUnavailableError("The source database is not available.")
        started = perf_counter()
        retrieval: RetrievalResult = self.retrieval_service.retrieve(request.question)
        proposal = self.sql_generation_service.generate(request.question, retrieval)
        snapshot = self.snapshot_provider(self.database_services.source)
        if snapshot.fingerprint != retrieval.index_fingerprint:
            raise QueryValidationError("The source schema changed since retrieval.")
        validation: SqlValidationResult = self.validation_service.validate(proposal.sql, snapshot)
        if not validation.passed:
            raise QueryValidationError(
                "The generated SQL did not pass deterministic validation: "
                + ", ".join(validation.blocking_errors)
            )
        result = self.executor.execute(
            SourceExecutionBinding(self.database_services.source), validation
        )
        answer = self.answer_service.generate(request.question, validation.sql, result)
        visualization = self.visualization_selector.select(result)
        logger.info(
            "basic_sql_pipeline_completed query_id=%s pipeline_run_id=%s row_count=%d "
            "truncated=%s elapsed_ms=%.2f",
            request.query_id,
            request.pipeline_run_id,
            result.row_count,
            result.truncated,
            (perf_counter() - started) * 1000,
        )
        return PipelineResult(
            query_id=request.query_id,
            pipeline_run_id=request.pipeline_run_id,
            question=request.question,
            retrieval=retrieval,
            proposal=proposal,
            validation=validation,
            result=result,
            answer=answer,
            visualization=visualization,
        )

    def _request(self, question: str) -> QueryRequest:
        if not question.strip():
            raise QueryValidationError("A non-empty question is required.")
        if len(question) > self.settings.max_question_length:
            raise QueryValidationError("The question exceeds the configured length limit.")
        return QueryRequest.create(question)
