"""Typed query identity and request models for the SQL pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class QueryRequest:
    """A bounded natural-language request owned by the backend."""

    question: str
    query_id: UUID
    pipeline_run_id: UUID

    @classmethod
    def create(cls, question: str) -> QueryRequest:
        """Create a request with backend-generated lifecycle identifiers."""

        return cls(question=question, query_id=uuid4(), pipeline_run_id=uuid4())


@dataclass(frozen=True, slots=True)
class QueryIdentity:
    """Opaque identifiers used to correlate one pipeline execution."""

    query_id: UUID
    pipeline_run_id: UUID
