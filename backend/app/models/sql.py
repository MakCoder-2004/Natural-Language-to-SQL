"""Structured SQL proposal and validation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


def sql_hash(sql: str) -> str:
    """Return a stable hash for the exact SQL text supplied to a boundary."""

    return sha256(sql.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SqlProposal:
    """Untrusted, structured output proposed by the SQL model."""

    sql: str
    interpretation: str
    tables_used: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    sql_hash: str

    @classmethod
    def create(
        cls,
        *,
        sql: str,
        interpretation: str,
        tables_used: tuple[str, ...] = (),
        assumptions: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> SqlProposal:
        """Create a proposal and compute its backend-owned SQL hash."""

        return cls(
            sql=sql,
            interpretation=interpretation,
            tables_used=tables_used,
            assumptions=assumptions,
            warnings=warnings,
            sql_hash=sql_hash(sql),
        )


@dataclass(frozen=True, slots=True)
class SqlValidationResult:
    """Deterministic authorization result for one exact SQL string."""

    passed: bool
    sql: str
    sql_hash: str
    referenced_schemas: tuple[str, ...]
    referenced_relations: tuple[str, ...]
    referenced_columns: tuple[str, ...]
    blocking_errors: tuple[str, ...]
    warnings: tuple[str, ...]
    applied_limits: tuple[str, ...]
    read_only: bool
    single_statement: bool

    @classmethod
    def rejected(
        cls,
        sql: str,
        *,
        errors: tuple[str, ...],
        warnings: tuple[str, ...] = (),
    ) -> SqlValidationResult:
        """Build a failed result without authorizing execution."""

        return cls(
            passed=False,
            sql=sql,
            sql_hash=sql_hash(sql),
            referenced_schemas=(),
            referenced_relations=(),
            referenced_columns=(),
            blocking_errors=errors,
            warnings=warnings,
            applied_limits=(),
            read_only=False,
            single_statement=False,
        )
