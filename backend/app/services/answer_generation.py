"""Service boundary for grounded answer generation."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.chains.answer_generation import GroundedAnswerOutput, build_answer_generation_chain
from app.chains.model_factory import create_chat_model
from app.config import Settings
from app.database.errors import ModelOutputError, ModelServiceError, translate_model_exception
from app.models.model_roles import ModelRole
from app.models.results import GroundedAnswer, QueryResult

logger = logging.getLogger(__name__)


class AnswerGenerationService:
    """Generate an answer from executed, normalized result data only."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.model_id = (
            settings.model_id_for(ModelRole.ANSWER_GENERATION) if chain is None else None
        )
        self.chain = chain or build_answer_generation_chain(
            create_chat_model(settings, ModelRole.ANSWER_GENERATION)
        )

    def generate(self, question: str, sql: str, result: QueryResult) -> GroundedAnswer:
        """Generate a grounded answer without passing raw database objects onward."""

        try:
            logger.info(
                "model_invocation role=%s model_id=%s",
                ModelRole.ANSWER_GENERATION.value,
                getattr(self, "model_id", None),
            )
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
                raise ModelOutputError("The answer model returned an unexpected response.")
            return GroundedAnswer(
                answer=output.answer,
                caveats=tuple(output.caveats),
                evidence_summary=output.evidence_summary,
            )
        except ModelServiceError:
            raise
        except Exception as exc:
            raise translate_model_exception(
                "The answer model could not summarize the result.", exc
            ) from exc
