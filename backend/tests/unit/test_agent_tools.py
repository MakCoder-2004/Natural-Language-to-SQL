from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from app.agent.controlled_agent import ControlledAgent
from app.agent.policies import ALLOWED_TOOL_NAMES, AgentPolicy
from app.agent.tools import BoundedToolSet
from app.database.errors import QueryExecutionError
from app.models.query import QueryRequest
from app.workflow.errors import WorkflowError
from app.workflow.state import QueryState


class FakeRetrieval:
    def retrieve(self, question: str) -> Any:
        return {"question": question}


class FakeSqlGeneration:
    def generate(self, question: str, retrieval: Any) -> Any:
        return {"question": question, "retrieval": retrieval}


class FakeExecutor:
    def execute(self, binding: Any, validation: Any) -> Any:
        return {"binding": binding, "validation": validation}


def _tool_set(state: QueryState = QueryState.SCHEMA_RETRIEVED) -> BoundedToolSet:
    return BoundedToolSet(
        retrieval_service=FakeRetrieval(),  # type: ignore[arg-type]
        sql_generation_service=FakeSqlGeneration(),  # type: ignore[arg-type]
        executor=FakeExecutor(),  # type: ignore[arg-type]
        database_services=None,
        policy=AgentPolicy(
            query_id=uuid4(), state=state, execution_mode="REVIEW", correction_attempts=0
        ),
    )


def test_controlled_agent_exposes_exact_allowlist() -> None:
    agent = ControlledAgent(_tool_set())
    assert agent.tool_names == ALLOWED_TOOL_NAMES
    assert {tool.name for tool in agent.tools} == ALLOWED_TOOL_NAMES


def test_clarification_state_cannot_use_tools() -> None:
    tool_set = _tool_set(QueryState.CLARIFICATION_REQUIRED)
    with pytest.raises(WorkflowError):
        tool_set.get_relevant_schema("question")


def test_execution_requires_backend_authorization() -> None:
    tool_set = _tool_set(QueryState.APPROVED)
    with pytest.raises(QueryExecutionError, match="not been authorized"):
        tool_set.execute_readonly_sql()


def test_execute_tool_has_no_model_controlled_arguments() -> None:
    execute_tool = next(
        tool
        for tool in ControlledAgent(_tool_set(QueryState.APPROVED)).tools
        if tool.name == "execute_readonly_sql"
    )
    assert getattr(execute_tool.args_schema, "model_fields", {}) == {}


def test_query_identity_is_backend_owned() -> None:
    request = QueryRequest.create("question")
    assert request.query_id != uuid4()
