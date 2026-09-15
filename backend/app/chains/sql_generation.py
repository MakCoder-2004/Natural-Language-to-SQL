"""LCEL chain for structured SQL proposals."""

from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ConfigDict, Field


class SqlProposalOutput(BaseModel):
    """Structured output expected from the SQL model."""

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1)
    interpretation: str = Field(min_length=1)
    tables_used: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def build_sql_generation_chain(model: Any) -> Any:
    """Build an LCEL prompt/model/parser chain for SQL proposal generation."""

    parser = PydanticOutputParser(pydantic_object=SqlProposalOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You generate safe, read-only PostgreSQL SQL for an analytics application.
Use only relations and columns present in the supplied schema context. Never invent
identifiers. Return exactly one structured object and no markdown.

The SQL must be one read-only SELECT statement. Do not use INSERT, UPDATE, DELETE,
MERGE, DDL, transaction control, or multiple statements. The tables_used field is
explanatory only; the backend independently validates the SQL.

{format_instructions}""",
            ),
            (
                "human",
                """Question:
{question}

Relevant schema context:
{schema_context}

PostgreSQL dialect guidance:
Use PostgreSQL syntax and quote identifiers only when required. Prefer explicit
qualified identifiers when joins could be ambiguous.""",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())
    return prompt | model | parser
