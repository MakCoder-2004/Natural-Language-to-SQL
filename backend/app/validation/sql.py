"""Conservative PostgreSQL SQL validation against current source metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.config import Settings
from app.database.models import RelationMetadata, SourceSchemaSnapshot
from app.models.sql import SqlValidationResult, sql_hash

_DISALLOWED_KEYS = frozenset(
    {
        "alter",
        "attach",
        "copy",
        "command",
        "commit",
        "create",
        "delete",
        "detach",
        "drop",
        "grant",
        "insert",
        "merge",
        "pragma",
        "revoke",
        "rollback",
        "set",
        "savepoint",
        "transaction",
        "truncate",
        "update",
        "use",
        "into",
        "lock",
    }
)

_DISALLOWED_FUNCTIONS = frozenset(
    {
        "dblink",
        "lo_close",
        "lo_create",
        "lo_export",
        "lo_import",
        "lo_unlink",
        "nextval",
        "pg_advisory_lock",
        "pg_advisory_lock_shared",
        "pg_advisory_unlock",
        "pg_advisory_unlock_all",
        "pg_advisory_unlock_shared",
        "pg_cancel_backend",
        "pg_sleep",
        "pg_sleep_for",
        "pg_sleep_until",
        "pg_terminate_backend",
        "set_config",
        "setval",
    }
)


@dataclass(frozen=True, slots=True)
class _RelationReference:
    schema_name: str
    relation_name: str
    alias: str | None


class SqlValidationService:
    """Authorize only one read-only SELECT against the current source snapshot."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def validate(
        self,
        sql: str,
        source_snapshot: SourceSchemaSnapshot,
    ) -> SqlValidationResult:
        """Parse and validate exact SQL without relying on model metadata."""

        if not sql.strip():
            return SqlValidationResult.rejected(sql, errors=("empty_sql",))
        try:
            statements = parse(sql, read="postgres")
        except ParseError:
            return SqlValidationResult.rejected(sql, errors=("parse_error",))
        if len(statements) != 1:
            return SqlValidationResult.rejected(sql, errors=("multiple_statements",))

        statement = statements[0]
        if not isinstance(statement, (exp.Select, exp.Union)):
            return SqlValidationResult.rejected(
                sql, errors=("not_read_only",), warnings=("Only SELECT statements are allowed.",)
            )
        if any(node.key in _DISALLOWED_KEYS for node in statement.walk()):
            return SqlValidationResult.rejected(sql, errors=("not_read_only",))
        if any(self._function_name(node) in _DISALLOWED_FUNCTIONS for node in statement.walk()):
            return SqlValidationResult.rejected(sql, errors=("suspicious_function",))

        source_relations: dict[tuple[str, str], RelationMetadata] = {
            (schema.name.lower(), relation.name.lower()): relation
            for schema in source_snapshot.schemas
            for relation in schema.relations
        }
        cte_names = {
            alias.name.lower()
            for with_expression in statement.find_all(exp.With)
            for alias in with_expression.find_all(exp.TableAlias)
            if alias.name
        }
        references, errors = self._relations(
            statement, source_relations, cte_names, source_snapshot_scope=source_snapshot.scope
        )
        if errors:
            return SqlValidationResult.rejected(sql, errors=tuple(errors))

        column_errors, referenced_columns = self._columns(statement, references, source_relations)
        if column_errors:
            return SqlValidationResult.rejected(
                sql,
                errors=tuple(column_errors),
            )

        schemas = tuple(sorted({reference.schema_name for reference in references}))
        relations = tuple(
            sorted(
                {f"{reference.schema_name}.{reference.relation_name}" for reference in references}
            )
        )
        return SqlValidationResult(
            passed=True,
            sql=sql,
            sql_hash=sql_hash(sql),
            referenced_schemas=schemas,
            referenced_relations=relations,
            referenced_columns=tuple(sorted(referenced_columns)),
            blocking_errors=(),
            warnings=(),
            applied_limits=self._applied_limits(),
            read_only=True,
            single_statement=True,
        )

    def _relations(
        self,
        statement: exp.Expression,
        source_relations: dict[tuple[str, str], RelationMetadata],
        cte_names: set[str],
        source_snapshot_scope: tuple[str, ...],
    ) -> tuple[tuple[_RelationReference, ...], list[str]]:
        references: list[_RelationReference] = []
        errors: list[str] = []
        for table in statement.find_all(exp.Table):
            table_name = table.name
            if table_name.lower() in cte_names:
                continue
            schema_name = table.db
            if table.catalog:
                errors.append("index_database_reference")
                continue
            if schema_name and schema_name.lower() not in {
                name.lower() for name in source_snapshot_scope
            }:
                errors.append("disallowed_schema")
                continue
            candidates = (
                ((schema_name.lower(), table_name.lower()),)
                if schema_name
                else tuple(key for key in source_relations if key[1] == table_name.lower())
            )
            matching_candidates = tuple(key for key in candidates if key in source_relations)
            if not schema_name and len(matching_candidates) > 1:
                errors.append("ambiguous_relation")
                continue
            matching = matching_candidates[0] if matching_candidates else None
            if matching is None:
                errors.append("unknown_relation")
                continue
            references.append(
                _RelationReference(
                    schema_name=source_relations[matching].schema_name,
                    relation_name=source_relations[matching].name,
                    alias=table.alias or None,
                )
            )
        if not references and not errors:
            # SELECT 1 is safe and does not reference a source relation.
            return (), []
        return tuple(references), errors

    def _columns(
        self,
        statement: exp.Expression,
        references: tuple[_RelationReference, ...],
        source_relations: dict[tuple[str, str], RelationMetadata],
    ) -> tuple[list[str], set[str]]:
        errors: list[str] = []
        referenced: set[str] = set()
        by_name = {reference.relation_name.lower(): reference for reference in references}
        by_alias = {
            reference.alias.lower(): reference
            for reference in references
            if reference.alias is not None
        }
        cte_columns = {
            cte.alias.lower(): {
                expression.alias_or_name.lower()
                for expression in cte.this.expressions
                if expression.alias_or_name
            }
            for with_expression in statement.find_all(exp.With)
            for cte in with_expression.expressions
        }
        for column in statement.find_all(exp.Column):
            column_name = column.name
            if column_name == "*":
                continue
            if column.table and column.table.lower() in cte_columns:
                if column_name.lower() not in cte_columns[column.table.lower()]:
                    errors.append("unknown_column")
                continue
            reference = by_alias.get(column.table.lower()) or by_name.get(column.table.lower())
            candidates = (reference,) if reference is not None else references
            matching_columns = [
                (
                    candidate,
                    source_relations[
                        (candidate.schema_name.lower(), candidate.relation_name.lower())
                    ],
                )
                for candidate in candidates
                if (candidate.schema_name.lower(), candidate.relation_name.lower())
                in source_relations
                and any(
                    source_column.name.lower() == column_name.lower()
                    for source_column in source_relations[
                        (candidate.schema_name.lower(), candidate.relation_name.lower())
                    ].columns
                )
            ]
            if not matching_columns:
                errors.append("unknown_column")
                continue
            if reference is None and len(matching_columns) > 1:
                errors.append("ambiguous_column")
                continue
            for matched_reference, _ in matching_columns:
                referenced.add(
                    f"{matched_reference.schema_name}.{matched_reference.relation_name}.{column_name}"
                )
        return errors, referenced

    def _applied_limits(self) -> tuple[str, ...]:
        """Describe backend resource controls attached to an authorization result."""

        if self.settings is None:
            return ()
        return ("statement_timeout", "max_returned_rows", "max_result_bytes")

    @staticmethod
    def _function_name(node: exp.Expression) -> str:
        """Return a normalized function name without trusting SQL text matching."""

        if isinstance(node, exp.Anonymous):
            return node.name.lower()
        if isinstance(node, exp.Func):
            return cast(str, node.sql_name()).lower()  # type: ignore[no-untyped-call]
        return ""
