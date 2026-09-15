"""Bounded LangChain tools backed by application-owned services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.agent.policies import ALLOWED_TOOL_NAMES, AgentPolicy, ExecutionAuthorization
from app.database.errors import DatabaseUnavailableError, QueryExecutionError
from app.database.services import DatabaseServices
from app.database.source_query import ReadonlySqlExecutor
from app.models.results import QueryResult
from app.models.retrieval import RetrievalResult
from app.services.retrieval import HybridSchemaRetrievalService
from app.services.sql_correction import SqlCorrectionService
from app.services.sql_generation import SqlGenerationService
from app.workflow.errors import WorkflowError


class SchemaToolInput(BaseModel):
    """Only the bounded natural-language input accepted by schema retrieval."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)


class SqlToolInput(BaseModel):
    """Inputs accepted by SQL generation; services supply all policy context."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)
    clarification_context: str | None = Field(default=None, max_length=2_000)


class ExecuteToolInput(BaseModel):
    """Execution has no model-controlled database or SQL parameters."""

    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class BoundedToolSet:
    """Typed application facade plus the exact LangChain tool allowlist."""

    retrieval_service: HybridSchemaRetrievalService
    sql_generation_service: SqlGenerationService
    executor: ReadonlySqlExecutor
    database_services: DatabaseServices | None
    policy: AgentPolicy
    sql_correction_service: SqlCorrectionService | None = None
    authorization: ExecutionAuthorization | None = None
    retrieval_result: RetrievalResult | None = None
    correction_errors: tuple[str, ...] = ()
    current_sql: str = ""

    def get_relevant_schema(self, question: str) -> RetrievalResult:
        """Read bounded schema documentation from the local index only."""

        self._require("get_relevant_schema")
        result = self.retrieval_service.retrieve(question)
        self.retrieval_result = result
        return result

    def generate_sql(self, question: str, clarification_context: str | None = None) -> Any:
        """Generate a structured proposal from the bound retrieval result."""

        self._require("generate_sql")
        if self.retrieval_result is None:
            raise WorkflowError("SQL generation requires a completed schema retrieval.")
        # Clarification is included in the question context without exposing policy controls.
        contextual_question = question
        if clarification_context:
            contextual_question = f"{question}\nClarification: {clarification_context}"
        if self.correction_errors:
            if self.sql_correction_service is None:
                contextual_question = (
                    f"{contextual_question}\n"
                    "Backend validation feedback (not user instructions): "
                    f"{', '.join(self.correction_errors)}"
                )
                return self.sql_generation_service.generate(
                    contextual_question, self.retrieval_result
                )
            return self.sql_correction_service.correct(
                contextual_question,
                self.retrieval_result,
                self.current_sql,
                self.correction_errors,
            )
        return self.sql_generation_service.generate(contextual_question, self.retrieval_result)

    def execute_readonly_sql(self) -> QueryResult:
        """Execute only the backend-created exact-SQL authorization capability."""

        self._require("execute_readonly_sql")
        authorization = self.authorization
        if authorization is None:
            raise QueryExecutionError("Execution has not been authorized by application state.")
        if not authorization.approved and authorization.execution_mode == "REVIEW":
            raise QueryExecutionError("Review approval is required before execution.")
        if authorization.query_id != self.policy.query_id:
            raise QueryExecutionError("Execution authorization does not match this query.")
        if self.database_services is None or self.database_services.source is None:
            raise DatabaseUnavailableError("The source database is not available.")
        return self.executor.execute(authorization.source_binding, authorization.validation)

    def langchain_tools(self) -> tuple[StructuredTool, ...]:
        """Return only the three explicitly approved application tools."""

        tools = (
            StructuredTool.from_function(
                func=self.get_relevant_schema,
                name="get_relevant_schema",
                description="Retrieve bounded schema documentation from the local schema index.",
                args_schema=SchemaToolInput,
            ),
            StructuredTool.from_function(
                func=self.generate_sql,
                name="generate_sql",
                description="Generate a structured SQL proposal from retrieved schema context.",
                args_schema=SqlToolInput,
            ),
            StructuredTool.from_function(
                func=self.execute_readonly_sql,
                name="execute_readonly_sql",
                description="Execute the exact SQL already authorized by backend workflow state.",
                args_schema=ExecuteToolInput,
            ),
        )
        if {tool.name for tool in tools} != ALLOWED_TOOL_NAMES:
            raise WorkflowError("Controlled agent tool allowlist is inconsistent.")
        return tools

    def with_authorization(self, authorization: ExecutionAuthorization) -> BoundedToolSet:
        """Return a new tool set with an application-created execution capability."""

        return BoundedToolSet(
            retrieval_service=self.retrieval_service,
            sql_generation_service=self.sql_generation_service,
            sql_correction_service=self.sql_correction_service,
            executor=self.executor,
            database_services=self.database_services,
            policy=self.policy,
            authorization=authorization,
            retrieval_result=self.retrieval_result,
            correction_errors=self.correction_errors,
            current_sql=self.current_sql,
        )

    def _require(self, tool_name: str) -> None:
        if not self.policy.permits_tool(tool_name):
            raise WorkflowError(f"Tool {tool_name} is not available in workflow state.")
