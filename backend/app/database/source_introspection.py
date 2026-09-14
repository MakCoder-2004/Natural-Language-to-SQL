"""Scoped PostgreSQL schema introspection and deterministic fingerprinting."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import Connection, inspect, text
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import SQLAlchemyError

from app.database.errors import (
    DatabaseSeparationError,
    DatabaseServiceError,
    SourceIntrospectionError,
    SourceSchemaNotFoundError,
)
from app.database.models import (
    Cardinality,
    DatabaseIdentity,
    ForeignKeyMetadata,
    IndexColumnMetadata,
    IndexMetadata,
    NullsOrder,
    PrimaryKeyMetadata,
    RelationKind,
    RelationMetadata,
    SchemaMetadata,
    SortOrder,
    SourceColumnMetadata,
    SourceSchemaSnapshot,
    UniqueConstraintMetadata,
)
from app.database.source_connection import SourceDatabase

_METADATA_VERSION = 1

_RELATION_COMMENTS_SQL = text(
    """
    SELECT
        c.relname AS relation_name,
        obj_description(c.oid, 'pg_class') AS relation_comment
    FROM pg_catalog.pg_class AS c
    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = :schema_name
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    """
)

_COLUMN_COMMENTS_SQL = text(
    """
    SELECT
        c.relname AS relation_name,
        a.attname AS column_name,
        col_description(c.oid, a.attnum) AS column_comment
    FROM pg_catalog.pg_class AS c
    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
    JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
    WHERE n.nspname = :schema_name
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND a.attnum > 0
      AND NOT a.attisdropped
    """
)

_INDEX_DETAILS_SQL = text(
    """
    SELECT
        index_class.relname AS index_name,
        index_data.indisunique AS is_unique,
        index_data.indisprimary AS is_primary,
        access_method.amname AS method,
        pg_get_expr(index_data.indpred, index_data.indrelid) AS predicate,
        index_key.ordinality AS position,
        CASE
            WHEN index_key.attnum > 0 THEN index_attribute.attname
            ELSE pg_get_indexdef(index_data.indexrelid, index_key.ordinality::integer, true)
        END AS indexed_name,
        CASE
            WHEN (index_data.indoption[index_key.ordinality::integer - 1] & 1) = 1 THEN 'desc'
            ELSE 'asc'
        END AS sort_order,
        CASE
            WHEN (index_data.indoption[index_key.ordinality::integer - 1] & 2) = 2 THEN 'first'
            ELSE 'last'
        END AS nulls_order,
        index_key.ordinality > index_data.indnkeyatts AS is_included
    FROM pg_catalog.pg_index AS index_data
    JOIN pg_catalog.pg_class AS index_class ON index_class.oid = index_data.indexrelid
    JOIN pg_catalog.pg_class AS relation_class ON relation_class.oid = index_data.indrelid
    JOIN pg_catalog.pg_namespace AS namespace_data
        ON namespace_data.oid = relation_class.relnamespace
    JOIN pg_catalog.pg_am AS access_method ON access_method.oid = index_class.relam
    CROSS JOIN LATERAL unnest(index_data.indkey) WITH ORDINALITY
        AS index_key(attnum, ordinality)
    LEFT JOIN pg_catalog.pg_attribute AS index_attribute
        ON index_attribute.attrelid = relation_class.oid
       AND index_attribute.attnum = index_key.attnum
    WHERE namespace_data.nspname = :schema_name
      AND relation_class.relname = :relation_name
    ORDER BY index_class.relname, index_key.ordinality
    """
)

_IDENTITY_SQL = text(
    """
    SELECT
        current_database() AS database_name,
        current_user AS user_name,
        current_setting('server_version') AS server_version
    """
)


class SourceIntrospector:
    """Collect technical metadata from one explicit source database."""

    def __init__(self, database: SourceDatabase) -> None:
        if not isinstance(database, SourceDatabase):
            raise DatabaseSeparationError("Source introspection requires a source database handle.")
        self.database = database

    def introspect(self) -> SourceSchemaSnapshot:
        """Return the approved source scope without reading business rows."""

        try:
            with self.database.connect() as connection:
                identity = _read_identity(connection)
                inspector = inspect(connection)
                available_schemas = set(inspector.get_schema_names())
                missing_schemas = [
                    schema_name
                    for schema_name in self.database.schema_scope
                    if schema_name not in available_schemas
                ]
                if missing_schemas:
                    raise SourceSchemaNotFoundError(
                        "One or more configured source schemas do not exist."
                    )

                schemas = tuple(
                    self._introspect_schema(connection, inspector, schema_name)
                    for schema_name in self.database.schema_scope
                )
        except SourceSchemaNotFoundError:
            raise
        except DatabaseServiceError:
            raise
        except SQLAlchemyError as exc:
            raise SourceIntrospectionError("The source schema could not be inspected.") from exc

        fingerprint = source_schema_fingerprint(self.database.schema_scope, schemas)
        return SourceSchemaSnapshot(
            identity=identity,
            scope=self.database.schema_scope,
            schemas=schemas,
            fingerprint=fingerprint,
        )

    def _introspect_schema(
        self,
        connection: Connection,
        inspector: Inspector,
        schema_name: str,
    ) -> SchemaMetadata:
        relation_kinds = _relation_kinds(inspector, schema_name)
        relation_names = set(relation_kinds)
        relation_comments, column_comments = _read_comments(connection, schema_name)
        relations = tuple(
            self._introspect_relation(
                connection,
                inspector,
                schema_name,
                relation_name,
                relation_kinds[relation_name],
                relation_comments,
                column_comments,
            )
            for relation_name in sorted(relation_names)
        )
        return SchemaMetadata(name=schema_name, relations=relations)

    def _introspect_relation(
        self,
        connection: Connection,
        inspector: Inspector,
        schema_name: str,
        relation_name: str,
        relation_kind: RelationKind,
        relation_comments: Mapping[str, str | None],
        column_comments: Mapping[tuple[str, str], str | None],
    ) -> RelationMetadata:
        raw_columns = inspector.get_columns(relation_name, schema=schema_name)
        columns = tuple(
            sorted(
                (
                    _column_metadata(
                        raw_column,
                        position,
                        column_comments.get((relation_name, _text(raw_column.get("name")) or "")),
                    )
                    for position, raw_column in enumerate(raw_columns, start=1)
                ),
                key=lambda column: (column.ordinal_position, column.name),
            )
        )

        primary_key = _primary_key_metadata(inspector, schema_name, relation_name)
        unique_constraints = _unique_constraints(inspector, schema_name, relation_name)
        foreign_keys = _foreign_keys(
            inspector,
            schema_name,
            relation_name,
            self.database.schema_scope,
            primary_key,
            unique_constraints,
        )
        indexes = _indexes(connection, inspector, schema_name, relation_name)

        return RelationMetadata(
            schema_name=schema_name,
            name=relation_name,
            kind=relation_kind,
            columns=columns,
            comment=relation_comments.get(relation_name),
            primary_key=primary_key,
            unique_constraints=unique_constraints,
            foreign_keys=foreign_keys,
            indexes=indexes,
        )


def source_schema_fingerprint(scope: tuple[str, ...], schemas: tuple[SchemaMetadata, ...]) -> str:
    """Hash canonical document-relevant metadata, excluding volatile database state."""

    payload = {
        "metadata_version": _METADATA_VERSION,
        "scope": sorted(set(scope)),
        "schemas": tuple(sorted(schemas, key=lambda schema: schema.name)),
    }
    canonical_payload = json.dumps(
        _canonical_value(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_payload).hexdigest()
    return f"sha256:{digest}"


def _read_identity(connection: Connection) -> DatabaseIdentity:
    row = connection.execute(_IDENTITY_SQL).mappings().one()
    return DatabaseIdentity(
        database_name=str(row["database_name"]),
        user_name=str(row["user_name"]),
        server_version=_text(row.get("server_version")),
    )


def _relation_kinds(inspector: Inspector, schema_name: str) -> dict[str, RelationKind]:
    relation_kinds: dict[str, RelationKind] = {
        name: "table" for name in inspector.get_table_names(schema=schema_name)
    }
    relation_kinds.update({name: "view" for name in inspector.get_view_names(schema=schema_name)})
    get_materialized_view_names = getattr(inspector, "get_materialized_view_names", None)
    if callable(get_materialized_view_names):
        relation_kinds.update(
            {name: "materialized_view" for name in get_materialized_view_names(schema=schema_name)}
        )
    return relation_kinds


def _read_comments(
    connection: Connection, schema_name: str
) -> tuple[dict[str, str | None], dict[tuple[str, str], str | None]]:
    relation_comments = {
        str(row["relation_name"]): _text(row.get("relation_comment"))
        for row in connection.execute(
            _RELATION_COMMENTS_SQL, {"schema_name": schema_name}
        ).mappings()
    }
    column_comments = {
        (str(row["relation_name"]), str(row["column_name"])): _text(row.get("column_comment"))
        for row in connection.execute(_COLUMN_COMMENTS_SQL, {"schema_name": schema_name}).mappings()
    }
    return relation_comments, column_comments


def _column_metadata(
    raw_column: Mapping[str, Any], fallback_position: int, comment: str | None
) -> SourceColumnMetadata:
    raw_name = _text(raw_column.get("name")) or ""
    raw_position = raw_column.get("ordinal_position")
    position = int(raw_position) if raw_position is not None else fallback_position
    raw_type = raw_column.get("type")
    identity = raw_column.get("identity")
    generated = raw_column.get("computed")
    return SourceColumnMetadata(
        name=raw_name,
        ordinal_position=position,
        data_type=str(raw_type),
        nullable=bool(raw_column.get("nullable", True)),
        default=_text(raw_column.get("default")),
        comment=comment if comment is not None else _text(raw_column.get("comment")),
        udt_name=_text(raw_column.get("udt_name")),
        identity=_text(identity),
        generated=_text(generated),
    )


def _primary_key_metadata(
    inspector: Inspector, schema_name: str, relation_name: str
) -> PrimaryKeyMetadata | None:
    raw = inspector.get_pk_constraint(relation_name, schema=schema_name)
    columns = _string_tuple(raw.get("constrained_columns"))
    if not columns:
        return None
    return PrimaryKeyMetadata(name=_text(raw.get("name")), columns=columns)


def _unique_constraints(
    inspector: Inspector, schema_name: str, relation_name: str
) -> tuple[UniqueConstraintMetadata, ...]:
    constraints = []
    for raw in inspector.get_unique_constraints(relation_name, schema=schema_name):
        columns = _string_tuple(raw.get("column_names"))
        if columns:
            constraints.append(
                UniqueConstraintMetadata(name=_text(raw.get("name")), columns=columns)
            )
    return tuple(
        sorted(constraints, key=lambda constraint: (constraint.name or "", constraint.columns))
    )


def _foreign_keys(
    inspector: Inspector,
    schema_name: str,
    relation_name: str,
    scope: tuple[str, ...],
    primary_key: PrimaryKeyMetadata | None,
    unique_constraints: tuple[UniqueConstraintMetadata, ...],
) -> tuple[ForeignKeyMetadata, ...]:
    relationships = []
    unique_column_sets = {frozenset(primary_key.columns)} if primary_key is not None else set()
    unique_column_sets.update(frozenset(constraint.columns) for constraint in unique_constraints)
    for raw in inspector.get_foreign_keys(relation_name, schema=schema_name):
        source_columns = _string_tuple(raw.get("constrained_columns"))
        target_relation = _text(raw.get("referred_table"))
        target_schema = _text(raw.get("referred_schema")) or schema_name
        if not source_columns or not target_relation:
            continue
        if target_schema not in scope:
            continue
        target_columns = _string_tuple(raw.get("referred_columns"))
        options = raw.get("options")
        options_mapping = options if isinstance(options, Mapping) else {}
        cardinality = (
            "one_to_one" if frozenset(source_columns) in unique_column_sets else "many_to_one"
        )
        relationships.append(
            ForeignKeyMetadata(
                name=_text(raw.get("name")),
                source_columns=source_columns,
                target_schema=target_schema,
                target_relation=target_relation,
                target_columns=target_columns,
                on_update=_text(raw.get("onupdate")) or _text(options_mapping.get("onupdate")),
                on_delete=_text(raw.get("ondelete")) or _text(options_mapping.get("ondelete")),
                cardinality=cast(Cardinality, cardinality),
            )
        )
    return tuple(
        sorted(
            relationships,
            key=lambda relationship: (
                relationship.name or "",
                relationship.source_columns,
                relationship.target_schema,
                relationship.target_relation,
            ),
        )
    )


def _indexes(
    connection: Connection, inspector: Inspector, schema_name: str, relation_name: str
) -> tuple[IndexMetadata, ...]:
    rows = list(
        connection.execute(
            _INDEX_DETAILS_SQL,
            {"schema_name": schema_name, "relation_name": relation_name},
        ).mappings()
    )
    if not rows:
        return _fallback_indexes(inspector, schema_name, relation_name)

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["index_name"]), []).append(cast(Mapping[str, Any], row))

    indexes = []
    for index_name, index_rows in grouped.items():
        key_columns = [row for row in index_rows if not bool(row["is_included"])]
        included_columns = tuple(
            str(row["indexed_name"]) for row in index_rows if bool(row["is_included"])
        )
        columns = tuple(
            IndexColumnMetadata(
                name=str(row["indexed_name"]),
                sort_order=cast(SortOrder, str(row["sort_order"])),
                nulls_order=cast(NullsOrder, str(row["nulls_order"])),
            )
            for row in key_columns
        )
        first_row = index_rows[0]
        indexes.append(
            IndexMetadata(
                name=index_name,
                columns=columns,
                unique=bool(first_row["is_unique"]),
                primary=bool(first_row["is_primary"]),
                method=_text(first_row.get("method")),
                predicate=_text(first_row.get("predicate")),
                included_columns=included_columns,
            )
        )
    return tuple(sorted(indexes, key=lambda index: index.name))


def _fallback_indexes(
    inspector: Inspector, schema_name: str, relation_name: str
) -> tuple[IndexMetadata, ...]:
    indexes = []
    for raw in inspector.get_indexes(relation_name, schema=schema_name):
        columns = tuple(
            IndexColumnMetadata(name=name) for name in _string_tuple(raw.get("column_names"))
        )
        name = _text(raw.get("name"))
        if name:
            indexes.append(
                IndexMetadata(
                    name=name,
                    columns=columns,
                    unique=bool(raw.get("unique", False)),
                )
            )
    return tuple(sorted(indexes, key=lambda index: index.name))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if item is not None)


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _canonical_value(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {
            field_name: _canonical_value(getattr(value, field_name))
            for field_name in value.__dataclass_fields__
        }
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    return value
