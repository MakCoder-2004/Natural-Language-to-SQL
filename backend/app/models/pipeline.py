"""Complete internal result of the basic SQL pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.results import GroundedAnswer, QueryResult
from app.models.retrieval import RetrievalResult
from app.models.sql import SqlProposal, SqlValidationResult
from app.models.visualization import VisualizationSelection


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Inspectable result of one question-to-result execution."""

    query_id: UUID
    pipeline_run_id: UUID
    question: str
    retrieval: RetrievalResult
    proposal: SqlProposal
    validation: SqlValidationResult
    result: QueryResult
    answer: GroundedAnswer
    visualization: VisualizationSelection
