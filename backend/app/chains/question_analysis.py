"""LCEL chain for structured question interpretation and ambiguity detection."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ConfigDict, Field


class QuestionAnalysisOutput(BaseModel):
    """Strict structured output expected from the question-analysis model."""

    model_config = ConfigDict(extra="forbid")

    classification: Literal["ANSWERABLE", "CLARIFICATION_REQUIRED", "IMPOSSIBLE", "UNSUPPORTED"]
    requested_metric: str = Field(min_length=1)
    entities: list[str] | None = None
    filters: list[str] | None = None
    time_range: str | None = None
    grouping: list[str] | None = None
    ordering: str | None = None
    limit: int | None = Field(default=None, ge=1)
    likely_source_tables: list[str] | None = None
    ambiguous_terms: list[str] | None = None
    clarification_question: str | None = None
    clarification_choices: list[str] | None = Field(default=None, max_length=5)
    answerability_reason: str = Field(min_length=1)
    warnings: list[str] | None = None


def build_question_analysis_chain(model: Any) -> Any:
    """Build an LCEL chain that returns a strict question analysis object."""

    parser = PydanticOutputParser(pydantic_object=QuestionAnalysisOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Analyze a natural-language analytics question for a PostgreSQL query workflow.
Classify it as ANSWERABLE, CLARIFICATION_REQUIRED, IMPOSSIBLE, or UNSUPPORTED.
Material ambiguity must require clarification rather than a guessed interpretation.
Never request credentials, connection details, arbitrary database inspection, or write access.
Return exactly one structured object and no markdown.

{format_instructions}""",
            ),
            (
                "human",
                """Question:
{question}

Clarification context, if any:
{clarification_context}""",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())
    return prompt | model | parser
