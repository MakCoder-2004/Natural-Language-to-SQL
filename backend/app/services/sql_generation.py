"""Service boundary for structured SQL proposal generation."""

from __future__ import annotations

import logging
from typing import Any

from app.chains.model_factory import create_chat_model
from app.chains.sql_generation import SqlProposalOutput, build_sql_generation_chain
from app.config import Settings
from app.database.errors import ModelOutputError, ModelServiceError, translate_model_exception
from app.models.model_roles import ModelRole
from app.models.retrieval import RetrievalResult
from app.models.sql import SqlProposal
from app.telemetry import emit_event

logger = logging.getLogger(__name__)


class SqlGenerationService:
    """Generate untrusted SQL proposals from bounded retrieved context."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.model_id = settings.model_id_for(ModelRole.SQL_GENERATION) if chain is None else None
        self.chain = chain or build_sql_generation_chain(
            create_chat_model(settings, ModelRole.SQL_GENERATION)
        )

    def generate(self, question: str, retrieval: RetrievalResult) -> SqlProposal:
        """Generate and structurally validate one SQL proposal."""

        if not question.strip():
            raise ModelServiceError("A non-empty question is required for SQL generation.")
        try:
            emit_event(
                logger,
                "model_invocation",
                model_role=ModelRole.SQL_GENERATION.value,
                model_id=getattr(self, "model_id", None),
            )
            output = self.chain.invoke(
                {"question": question, "schema_context": retrieval.context_text}
            )
            if not isinstance(output, SqlProposalOutput):
                raise ModelOutputError("The SQL model returned an unexpected response.")
            return SqlProposal.create(
                sql=output.sql,
                interpretation=output.interpretation,
                tables_used=tuple(output.tables_used),
                assumptions=tuple(output.assumptions),
                warnings=tuple(output.warnings),
            )
        except ModelServiceError:
            raise
        except Exception as exc:
            raise translate_model_exception(
                "The SQL model could not produce a valid proposal.", exc
            ) from exc
