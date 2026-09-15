"""Service boundary for the separately configured SQL-correction model."""

from __future__ import annotations

import logging
from typing import Any

from app.chains.model_factory import create_chat_model
from app.chains.sql_correction import build_sql_correction_chain
from app.chains.sql_generation import SqlProposalOutput
from app.config import Settings
from app.database.errors import ModelOutputError, ModelServiceError, translate_model_exception
from app.models.model_roles import ModelRole
from app.models.retrieval import RetrievalResult
from app.models.sql import SqlProposal
from app.telemetry import emit_event

logger = logging.getLogger(__name__)


class SqlCorrectionService:
    """Repair rejected proposals without authorizing or executing them."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.model_id = settings.model_id_for(ModelRole.SQL_CORRECTION) if chain is None else None
        self.chain = chain or build_sql_correction_chain(
            create_chat_model(settings, ModelRole.SQL_CORRECTION)
        )

    def correct(
        self,
        question: str,
        retrieval: RetrievalResult,
        sql: str,
        validation_errors: tuple[str, ...],
    ) -> SqlProposal:
        """Return a new untrusted proposal from bounded validation feedback."""

        try:
            emit_event(
                logger,
                "model_invocation",
                model_role=ModelRole.SQL_CORRECTION.value,
                model_id=getattr(self, "model_id", None),
            )
            output = self.chain.invoke(
                {
                    "question": question,
                    "schema_context": retrieval.context_text,
                    "sql": sql,
                    "validation_errors": ", ".join(validation_errors),
                }
            )
            if not isinstance(output, SqlProposalOutput):
                raise ModelOutputError("The SQL correction model returned an unexpected response.")
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
                "The SQL correction model could not repair the proposal.", exc
            ) from exc
