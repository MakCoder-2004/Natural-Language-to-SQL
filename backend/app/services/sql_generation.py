"""Service boundary for structured SQL proposal generation."""

from __future__ import annotations

from typing import Any

from app.chains.model_factory import create_chat_model
from app.chains.sql_generation import SqlProposalOutput, build_sql_generation_chain
from app.config import Settings
from app.database.errors import ModelServiceError
from app.models.retrieval import RetrievalResult
from app.models.sql import SqlProposal


class SqlGenerationService:
    """Generate untrusted SQL proposals from bounded retrieved context."""

    def __init__(self, settings: Settings, *, chain: Any | None = None) -> None:
        self.settings = settings
        self.chain = chain or build_sql_generation_chain(
            create_chat_model(settings, settings.sql_model)
        )

    def generate(self, question: str, retrieval: RetrievalResult) -> SqlProposal:
        """Generate and structurally validate one SQL proposal."""

        if not question.strip():
            raise ModelServiceError("A non-empty question is required for SQL generation.")
        try:
            output = self.chain.invoke(
                {"question": question, "schema_context": retrieval.context_text}
            )
            if not isinstance(output, SqlProposalOutput):
                raise ModelServiceError("The SQL model returned an unexpected response.")
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
            raise ModelServiceError("The SQL model could not produce a valid proposal.") from exc
