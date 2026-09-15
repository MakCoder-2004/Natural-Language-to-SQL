"""Deterministic LCEL workflow for the bounded natural-language SQL path."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any, cast

from langchain_core.runnables import RunnableBranch, RunnableLambda

from app.agent.controlled_agent import ControlledAgent
from app.agent.policies import AgentPolicy, ExecutionAuthorization
from app.agent.tools import BoundedToolSet
from app.config import Settings
from app.database.models import SourceSchemaSnapshot
from app.database.services import DatabaseServices
from app.database.source_execution import SourceExecutionBinding
from app.database.source_introspection import SourceIntrospector
from app.database.source_query import ReadonlySqlExecutor
from app.models.query import QueryRequest
from app.models.sql import SqlProposal, SqlValidationResult
from app.services.answer_generation import AnswerGenerationService
from app.services.question_analysis import QuestionAnalysisService
from app.services.retrieval import HybridSchemaRetrievalService
from app.services.sql_generation import SqlGenerationService
from app.services.visualization import VisualizationSelector
from app.validation.sql import SqlValidationService
from app.workflow.errors import WorkflowError
from app.workflow.state import (
    ExecutionMode,
    QueryState,
    QueryWorkflowState,
    pipeline_result_from_state,
)
from app.workflow.transitions import transition

logger = logging.getLogger(__name__)


class DeterministicQueryWorkflow:
    """Run one query through backend-owned state transitions and LCEL nodes."""

    def __init__(
        self,
        settings: Settings,
        database_services: DatabaseServices | None,
        *,
        analysis_service: Any | None = None,
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
        self.analysis_service = analysis_service or QuestionAnalysisService(settings)
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
        self._workflow = self._build_workflow()

    def run(
        self,
        question: str,
        *,
        execution_mode: ExecutionMode = "REVIEW",
        clarification_context: str | None = None,
    ) -> QueryWorkflowState:
        """Start a workflow and stop at review, clarification, failure, or completion."""

        request = self._request(question)
        state = QueryWorkflowState.from_request(
            request, execution_mode=execution_mode, clarification_context=clarification_context
        )
        return cast(QueryWorkflowState, self._workflow.invoke(state))

    def resume_clarification(
        self,
        state: QueryWorkflowState,
        clarification_context: str,
    ) -> QueryWorkflowState:
        """Resume only a clarification-pending query with user-provided context."""

        if state.state != QueryState.CLARIFICATION_REQUIRED:
            raise WorkflowError("Only a clarification-pending query can be resumed.")
        if not clarification_context.strip():
            raise WorkflowError("Clarification context cannot be empty.")
        resumed = state.evolve(clarification_context=clarification_context)
        resumed = transition(resumed, QueryState.ANALYZING, reason="clarification received")
        analyzed = self._analysis_node(resumed)
        if analyzed.state != QueryState.SCHEMA_RETRIEVED:
            return analyzed
        return cast(QueryWorkflowState, self._answerable_workflow.invoke(analyzed))

    def edit_sql(self, state: QueryWorkflowState, sql: str) -> QueryWorkflowState:
        """Treat edited SQL as untrusted input and return it to validation."""

        if state.state != QueryState.READY_FOR_REVIEW:
            raise WorkflowError("Only a review-ready query can be edited.")
        if state.proposal is None:
            raise WorkflowError("The query has no SQL proposal to edit.")
        edited_proposal = SqlProposal.create(
            sql=sql,
            interpretation=state.proposal.interpretation,
            tables_used=state.proposal.tables_used,
            assumptions=state.proposal.assumptions,
            warnings=state.proposal.warnings,
        )
        edited = state.evolve(proposal=edited_proposal, validation=None, validated_sql_hash=None)
        edited = transition(edited, QueryState.EDITED, reason="user edited SQL")
        return self._validate_node(edited)

    def approve(self, state: QueryWorkflowState) -> QueryWorkflowState:
        """Approve the exact validated SQL version in Review Mode."""

        if state.state != QueryState.READY_FOR_REVIEW:
            raise WorkflowError("Only a review-ready query can be approved.")
        if state.execution_mode != "REVIEW" or state.validation is None:
            raise WorkflowError("Approval is available only for a validated Review Mode query.")
        approved = state.evolve(approval_sql_hash=state.validation.sql_hash)
        return transition(approved, QueryState.APPROVED, reason="review approval received")

    def execute_approved(self, state: QueryWorkflowState) -> QueryWorkflowState:
        """Revalidate and execute an approved Review Mode query."""

        if state.state != QueryState.APPROVED:
            raise WorkflowError("Only an approved query can be executed.")
        return cast(QueryWorkflowState, self._execute_workflow.invoke(state))

    def result(self, state: QueryWorkflowState) -> Any:
        """Return the legacy complete result only after workflow completion."""

        if state.state != QueryState.COMPLETED:
            raise WorkflowError("A pipeline result is available only after completion.")
        return pipeline_result_from_state(state)

    def controlled_agent(self, state: QueryWorkflowState) -> ControlledAgent:
        """Build an inspectable agent facade with tools allowed in this state."""

        return ControlledAgent(self._tool_set(state))

    def _build_workflow(self) -> Any:
        """Compose analysis and answerable stages using LCEL branching."""

        self._answerable_workflow: Any = (
            RunnableLambda(self._retrieve_node)
            | RunnableLambda(self._generate_node)
            | RunnableLambda(self._validate_node)
            | RunnableBranch(
                (
                    lambda state: state.state == QueryState.READY_FOR_REVIEW,
                    RunnableLambda(lambda state: state),
                ),
                (
                    lambda state: state.state == QueryState.COMPLETED,
                    RunnableLambda(lambda state: state),
                ),
                (
                    lambda state: state.state == QueryState.FAILED,
                    RunnableLambda(lambda state: state),
                ),
                self._execute_workflow,
            )
        )
        analysis_route: Any = RunnableBranch(
            (
                lambda state: state.state in {QueryState.CLARIFICATION_REQUIRED, QueryState.FAILED},
                RunnableLambda(lambda state: state),
            ),
            self._answerable_workflow,
        )
        return RunnableLambda(self._analysis_node) | analysis_route

    @property
    def _execute_workflow(self) -> Any:
        """Build the execution and result stages as an LCEL sequence."""

        return (
            RunnableLambda(self._execution_gate_node)
            | RunnableLambda(self._execute_node)
            | RunnableLambda(self._answer_node)
            | RunnableLambda(self._visualization_node)
            | RunnableLambda(self._complete_node)
        )

    def _request(self, question: str) -> QueryRequest:
        if not question.strip():
            raise WorkflowError("A non-empty question is required.")
        if len(question) > self.settings.max_question_length:
            raise WorkflowError("The question exceeds the configured length limit.")
        return QueryRequest.create(question)

    def _analysis_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        started = perf_counter()
        if state.state == QueryState.RECEIVED:
            state = transition(state, QueryState.ANALYZING, reason="begin question analysis")
        try:
            analysis = self.analysis_service.analyze(state.question, state.clarification_context)
        except Exception as exc:
            return self._failed(
                state,
                code=getattr(exc, "error_code", "model_error"),
                message="The question could not be analyzed safely.",
                stage="analysis",
            )
        state = state.evolve(
            analysis=analysis,
            stage_timings_ms={**state.stage_timings_ms, "analysis": _milliseconds(started)},
        )
        if analysis.classification == "CLARIFICATION_REQUIRED":
            return transition(
                state, QueryState.CLARIFICATION_REQUIRED, reason="clarification required"
            )
        if analysis.classification in {"IMPOSSIBLE", "UNSUPPORTED"}:
            return self._failed(
                state,
                code=analysis.classification.lower(),
                message=analysis.answerability_reason,
                stage="analysis",
            )
        return transition(state, QueryState.SCHEMA_RETRIEVED, reason="question is answerable")

    def _retrieve_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        started = perf_counter()
        tool_set = self._tool_set(state)
        try:
            retrieval = tool_set.get_relevant_schema(state.question)
        except Exception as exc:
            return self._failed(
                state,
                code=getattr(exc, "error_code", "index_error"),
                message="The schema index could not provide relevant context.",
                stage="retrieval",
            )
        return state.evolve(
            retrieval=retrieval,
            index_fingerprint=retrieval.index_fingerprint,
            stage_timings_ms={**state.stage_timings_ms, "retrieval": _milliseconds(started)},
        )

    def _generate_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        if state.retrieval is None:
            return self._failed(
                state,
                code="missing_retrieval",
                message="Schema retrieval was not completed.",
                stage="generation",
            )
        started = perf_counter()
        tool_set = self._tool_set(state, retrieval_result=state.retrieval)
        try:
            proposal = tool_set.generate_sql(state.question, state.clarification_context)
        except Exception as exc:
            return self._failed(
                state,
                code=getattr(exc, "error_code", "model_error"),
                message="The SQL proposal could not be generated safely.",
                stage="sql_generation",
            )
        generated = state.evolve(
            proposal=proposal,
            validation=None,
            validated_sql_hash=None,
            stage_timings_ms={**state.stage_timings_ms, "sql_generation": _milliseconds(started)},
        )
        if generated.state == QueryState.SCHEMA_RETRIEVED:
            return transition(
                generated, QueryState.SQL_GENERATED, reason="structured SQL generated"
            )
        return generated

    def _validate_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        if state.proposal is None:
            return self._failed(
                state,
                code="missing_proposal",
                message="SQL generation did not produce a proposal.",
                stage="validation",
            )
        if self.database_services is None or self.database_services.source is None:
            return self._failed(
                state,
                code="database_unavailable",
                message="The source database is not available.",
                stage="validation",
            )
        if state.state == QueryState.SQL_GENERATED:
            validating = transition(
                state, QueryState.VALIDATING, reason="begin deterministic validation"
            )
        elif state.state == QueryState.EDITED:
            validating = transition(state, QueryState.VALIDATING, reason="validate edited SQL")
        else:
            validating = state
        try:
            snapshot = self.snapshot_provider(self.database_services.source)
        except Exception:
            return self._failed(
                validating,
                code="source_introspection_error",
                message="The source schema could not be inspected safely.",
                stage="validation",
            )
        if (
            validating.retrieval is not None
            and snapshot.fingerprint != validating.retrieval.index_fingerprint
        ):
            return self._failed(
                validating,
                code="source_schema_changed",
                message="The source schema changed since schema retrieval.",
                stage="validation",
            )
        proposal = validating.proposal
        if proposal is None:
            return self._failed(
                validating,
                code="missing_proposal",
                message="SQL generation did not produce a proposal.",
                stage="validation",
            )
        try:
            validation: SqlValidationResult = self.validation_service.validate(
                proposal.sql, snapshot
            )
        except Exception:
            return self._failed(
                validating,
                code="query_validation_error",
                message="The SQL could not be validated safely.",
                stage="validation",
            )
        validated = validating.evolve(
            validation=validation,
            validated_sql_hash=validation.sql_hash if validation.passed else None,
            source_fingerprint=snapshot.fingerprint,
        )
        if not validation.passed:
            if validated.correction_attempts < self.settings.max_correction_retries:
                corrected = transition(
                    validated, QueryState.SQL_CORRECTION, reason="validation requires correction"
                )
                corrected = corrected.evolve(correction_attempts=corrected.correction_attempts + 1)
                return self._correction_loop(corrected)
            return self._failed(
                validated,
                code="correction_exhausted",
                message="I couldn't generate a valid query after the allowed correction attempts.",
                stage="validation",
            )
        if validated.execution_mode == "AUTO":
            return transition(
                validated, QueryState.EXECUTING, reason="validated Auto Mode execution"
            )
        return transition(
            validated, QueryState.READY_FOR_REVIEW, reason="validated SQL ready for review"
        )

    def _correction_loop(self, state: QueryWorkflowState) -> QueryWorkflowState:
        """Perform bounded correction through explicit state transitions."""

        current = state
        while current.state == QueryState.SQL_CORRECTION:
            current = self._generate_node(
                transition(current, QueryState.SQL_GENERATED, reason="regenerate corrected SQL")
            )
            current = self._validate_node(current)
        return current

    def _execution_gate_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        if state.state == QueryState.READY_FOR_REVIEW:
            return self._failed(
                state,
                code="approval_required",
                message="Review approval is required before execution.",
                stage="execution_gate",
            )
        if state.state == QueryState.APPROVED:
            return transition(
                state, QueryState.EXECUTING, reason="approved query entering execution"
            )
        if state.state not in {QueryState.APPROVED, QueryState.EXECUTING}:
            return self._failed(
                state,
                code="execution_not_authorized",
                message="The workflow has not authorized execution.",
                stage="execution_gate",
            )
        return state

    def _execute_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        if self.database_services is None or self.database_services.source is None:
            return self._failed(
                state,
                code="database_unavailable",
                message="The source database is not available.",
                stage="execution",
            )
        if state.validation is None or state.proposal is None:
            return self._failed(
                state,
                code="execution_not_authorized",
                message="No validated SQL is available.",
                stage="execution",
            )
        started = perf_counter()
        try:
            snapshot = self.snapshot_provider(self.database_services.source)
            validation: SqlValidationResult = self.validation_service.validate(
                state.proposal.sql, snapshot
            )
        except Exception:
            return self._failed(
                state,
                code="execution_revalidation_failed",
                message="The exact SQL could not be revalidated before execution.",
                stage="execution",
            )
        if not validation.passed or validation.sql_hash != state.validated_sql_hash:
            return self._failed(
                state,
                code="execution_revalidation_failed",
                message="The exact SQL failed immediate execution revalidation.",
                stage="execution",
            )
        authorization = ExecutionAuthorization(
            query_id=state.query_id,
            validated_sql=validation.sql,
            sql_hash=validation.sql_hash,
            validation=validation,
            source_fingerprint=snapshot.fingerprint,
            source_binding=SourceExecutionBinding(self.database_services.source),
            execution_mode=state.execution_mode,
            approved=state.approval_sql_hash == validation.sql_hash,
            max_returned_rows=self.settings.max_returned_rows,
            max_result_bytes=self.settings.max_result_bytes,
        )
        authorized = state.evolve(validation=validation, source_fingerprint=snapshot.fingerprint)
        tool_set = self._tool_set(authorized, authorization=authorization)
        try:
            result = tool_set.execute_readonly_sql()
        except Exception as exc:
            return self._failed(
                authorized,
                code=getattr(exc, "error_code", "source_database_failure"),
                message="The database query could not be executed.",
                stage="execution",
            )
        executed = authorized.evolve(
            result=result,
            stage_timings_ms={**authorized.stage_timings_ms, "execution": _milliseconds(started)},
        )
        return transition(executed, QueryState.EXECUTED, reason="source query executed")

    def _answer_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        if state.result is None or state.proposal is None:
            return self._failed(
                state,
                code="missing_execution_result",
                message="No executed result is available.",
                stage="answer",
            )
        started = perf_counter()
        try:
            answer = self.answer_service.generate(state.question, state.proposal.sql, state.result)
        except Exception:
            return self._failed(
                state,
                code="answer_generation_error",
                message="The executed result could not be summarized safely.",
                stage="answer",
            )
        answered = state.evolve(
            answer=answer,
            stage_timings_ms={**state.stage_timings_ms, "answer": _milliseconds(started)},
        )
        return transition(answered, QueryState.ANSWER_GENERATED, reason="grounded answer generated")

    def _visualization_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        if state.result is None:
            return self._failed(
                state,
                code="missing_execution_result",
                message="No result is available for visualization.",
                stage="visualization",
            )
        return state.evolve(visualization=self.visualization_selector.select(state.result))

    def _complete_node(self, state: QueryWorkflowState) -> QueryWorkflowState:
        return transition(state, QueryState.COMPLETED, reason="workflow completed")

    def _tool_set(
        self,
        state: QueryWorkflowState,
        *,
        retrieval_result: Any | None = None,
        authorization: ExecutionAuthorization | None = None,
    ) -> BoundedToolSet:
        return BoundedToolSet(
            retrieval_service=self.retrieval_service,
            sql_generation_service=self.sql_generation_service,
            executor=self.executor,
            database_services=self.database_services,
            policy=AgentPolicy(
                query_id=state.query_id,
                state=state.state,
                execution_mode=state.execution_mode,
                correction_attempts=state.correction_attempts,
            ),
            authorization=authorization,
            retrieval_result=retrieval_result,
            correction_errors=(
                state.validation.blocking_errors
                if state.state == QueryState.SQL_CORRECTION and state.validation is not None
                else ()
            ),
        )

    def _failed(
        self,
        state: QueryWorkflowState,
        *,
        code: str,
        message: str,
        stage: str,
    ) -> QueryWorkflowState:
        from app.workflow.state import WorkflowErrorInfo

        failed = state.evolve(error=WorkflowErrorInfo(code=code, message=message, stage=stage))
        if failed.state == QueryState.FAILED:
            return failed
        return transition(failed, QueryState.FAILED, reason=code)


def _milliseconds(started: float) -> float:
    return round((perf_counter() - started) * 1000, 2)
