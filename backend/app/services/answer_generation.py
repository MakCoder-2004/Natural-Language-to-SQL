"""Service boundary for grounded answer generation."""

from __future__ import annotations

import json
from typing import Any

from app.chains.answer_generation import GroundedAnswerOutput, build_answer_generation_chain
from app.chains.model_factory import create_chat_model
from app.config import Settings
from app.database.errors import ModelServiceError
from app.models.results import GroundedAnswer, QueryResult


class AnswerGenerationService:
    """Generate an answer from executed, normalized result data only."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.chain = chain or build_answer_generation_chain(
            create_chat_model(settings, settings.answer_model)
        )

    def generate(self, question: str, sql: str, result: QueryResult) -> GroundedAnswer:
        """Generate a grounded answer without passing raw database objects onward."""

        try:
            result_json = json.dumps(
                {
                    "columns": result.columns,
                    "rows": result.rows,
                    "row_count": result.row_count,
                    "returned_row_count": result.returned_row_count,
                    "truncated": result.truncated,
                    "warnings": result.warnings,
                },
                default=str,
                separators=(",", ":"),
            )
            output = self.chain.invoke(
                {"question": question, "sql": sql, "result_json": result_json}
            )
            if not isinstance(output, GroundedAnswerOutput):
                raise ModelServiceError("The answer model returned an unexpected response.")
            return GroundedAnswer(
                answer=output.answer,
                caveats=tuple(output.caveats),
                evidence_summary=output.evidence_summary,
            )
        except ModelServiceError:
            raise
        except Exception as exc:
            raise ModelServiceError("The answer model could not summarize the result.") from exc
