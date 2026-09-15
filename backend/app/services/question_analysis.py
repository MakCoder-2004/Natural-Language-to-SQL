"""Service boundary for structured question analysis."""

from __future__ import annotations

import logging
from typing import Any

from app.chains.model_factory import create_chat_model
from app.chains.question_analysis import QuestionAnalysisOutput, build_question_analysis_chain
from app.config import Settings
from app.database.errors import ModelOutputError, ModelServiceError, translate_model_exception
from app.models.model_roles import ModelRole
from app.telemetry import emit_event
from app.workflow.state import QuestionAnalysis

logger = logging.getLogger(__name__)


class QuestionAnalysisService:
    """Analyze user intent without making execution or security decisions."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.model_id = (
            settings.model_id_for(ModelRole.QUESTION_ANALYSIS) if chain is None else None
        )
        self.chain = chain or build_question_analysis_chain(
            create_chat_model(settings, ModelRole.QUESTION_ANALYSIS)
        )

    def analyze(self, question: str, clarification_context: str | None = None) -> QuestionAnalysis:
        """Return a validated analysis or a safe model-service error."""

        if not question.strip():
            raise ModelServiceError("A non-empty question is required for analysis.")
        try:
            emit_event(
                logger,
                "model_invocation",
                model_role=ModelRole.QUESTION_ANALYSIS.value,
                model_id=getattr(self, "model_id", None),
            )
            output = self.chain.invoke(
                {
                    "question": question,
                    "clarification_context": clarification_context or "None",
                }
            )
            if not isinstance(output, QuestionAnalysisOutput):
                raise ModelOutputError(
                    "The question-analysis model returned an unexpected response."
                )
            return QuestionAnalysis(
                classification=output.classification,
                requested_metric=output.requested_metric,
                entities=tuple(output.entities or ()),
                filters=tuple(output.filters or ()),
                time_range=output.time_range,
                grouping=tuple(output.grouping or ()),
                ordering=output.ordering,
                limit=output.limit,
                likely_source_tables=tuple(output.likely_source_tables or ()),
                ambiguous_terms=tuple(output.ambiguous_terms or ()),
                clarification_question=output.clarification_question,
                clarification_choices=tuple(output.clarification_choices or ()),
                answerability_reason=output.answerability_reason,
                warnings=tuple(output.warnings or ()),
            )
        except ModelServiceError:
            raise
        except Exception as exc:
            raise translate_model_exception(
                "The question could not be analyzed safely.", exc
            ) from exc
