"""Service boundary for structured question analysis."""

from __future__ import annotations

from typing import Any

from app.chains.model_factory import create_chat_model
from app.chains.question_analysis import QuestionAnalysisOutput, build_question_analysis_chain
from app.config import Settings
from app.database.errors import ModelServiceError
from app.workflow.state import QuestionAnalysis


class QuestionAnalysisService:
    """Analyze user intent without making execution or security decisions."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.chain = chain or build_question_analysis_chain(
            create_chat_model(settings, settings.question_model)
        )

    def analyze(self, question: str, clarification_context: str | None = None) -> QuestionAnalysis:
        """Return a validated analysis or a safe model-service error."""

        if not question.strip():
            raise ModelServiceError("A non-empty question is required for analysis.")
        try:
            output = self.chain.invoke(
                {
                    "question": question,
                    "clarification_context": clarification_context or "None",
                }
            )
            if not isinstance(output, QuestionAnalysisOutput):
                raise ModelServiceError(
                    "The question-analysis model returned an unexpected response."
                )
            return QuestionAnalysis(
                classification=output.classification,
                requested_metric=output.requested_metric,
                entities=tuple(output.entities),
                filters=tuple(output.filters),
                time_range=output.time_range,
                grouping=tuple(output.grouping),
                ordering=output.ordering,
                limit=output.limit,
                likely_source_tables=tuple(output.likely_source_tables),
                ambiguous_terms=tuple(output.ambiguous_terms),
                clarification_question=output.clarification_question,
                clarification_choices=tuple(output.clarification_choices),
                answerability_reason=output.answerability_reason,
                warnings=tuple(output.warnings),
            )
        except ModelServiceError:
            raise
        except Exception as exc:
            raise ModelServiceError("The question could not be analyzed safely.") from exc
