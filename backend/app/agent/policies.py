"""Backend-owned policies for the bounded query agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from app.database.source_execution import SourceExecutionBinding
from app.models.sql import SqlValidationResult
from app.workflow.state import ExecutionMode, QueryState

ALLOWED_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {"get_relevant_schema", "generate_sql", "execute_readonly_sql"}
)


@dataclass(frozen=True, slots=True)
class AgentPolicy:
    """Immutable limits and current lifecycle context available to tools."""

    query_id: UUID
    state: QueryState
    execution_mode: ExecutionMode
    correction_attempts: int
    max_tool_calls: int = 3

    def permits_tool(self, tool_name: str) -> bool:
        """Return whether the named approved tool is available at this stage."""

        if tool_name not in ALLOWED_TOOL_NAMES:
            return False
        if tool_name == "execute_readonly_sql":
            return self.state in {QueryState.APPROVED, QueryState.EXECUTING}
        return self.state not in {QueryState.CLARIFICATION_REQUIRED, QueryState.FAILED}


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Backend-created capability required by the execution tool."""

    query_id: UUID
    validated_sql: str
    sql_hash: str
    validation: SqlValidationResult
    source_fingerprint: str
    source_binding: SourceExecutionBinding
    execution_mode: ExecutionMode
    approved: bool
    max_returned_rows: int
    max_result_bytes: int
