"""Typed, source-only models for PostgreSQL schema metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RelationKind = Literal["table", "view", "materialized_view"]
Cardinality = Literal["one_to_one", "many_to_one", "unknown"]
SortOrder = Literal["asc", "desc", "unknown"]
NullsOrder = Literal["first", "last", "unknown"]


@dataclass(frozen=True, slots=True)
class DatabaseIdentity:
    """Non-secret identity information returned by a database probe."""

    database_name: str
    user_name: str
    server_version: str | None = None


@dataclass(frozen=True, slots=True)
class SourceColumnMetadata:
    """Metadata for one source relation column."""

    name: str
    ordinal_position: int
    data_type: str
    nullable: bool
    default: str | None = None
    comment: str | None = None
    udt_name: str | None = None
    identity: str | None = None
    generated: str | None = None


@dataclass(frozen=True, slots=True)
class PrimaryKeyMetadata:
    """Primary-key metadata with its database-defined column order."""

    name: str | None
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniqueConstraintMetadata:
    """Unique-constraint metadata with its database-defined column order."""

    name: str | None
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForeignKeyMetadata:
    """A relationship from one source relation to another relation."""

    name: str | None
    source_columns: tuple[str, ...]
    target_schema: str
    target_relation: str
    target_columns: tuple[str, ...]
    on_update: str | None = None
    on_delete: str | None = None
    cardinality: Cardinality = "unknown"


@dataclass(frozen=True, slots=True)
class IndexColumnMetadata:
    """One ordered column or expression in a PostgreSQL index."""

    name: str
    sort_order: SortOrder = "unknown"
    nulls_order: NullsOrder = "unknown"


@dataclass(frozen=True, slots=True)
class IndexMetadata:
    """Relevant index metadata for a source relation."""

    name: str
    columns: tuple[IndexColumnMetadata, ...]
    unique: bool = False
    primary: bool = False
    method: str | None = None
    predicate: str | None = None
    included_columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationMetadata:
    """Technical metadata for a table, view, or materialized view."""

    schema_name: str
    name: str
    kind: RelationKind
    columns: tuple[SourceColumnMetadata, ...]
    comment: str | None = None
    primary_key: PrimaryKeyMetadata | None = None
    unique_constraints: tuple[UniqueConstraintMetadata, ...] = ()
    foreign_keys: tuple[ForeignKeyMetadata, ...] = ()
    indexes: tuple[IndexMetadata, ...] = ()


@dataclass(frozen=True, slots=True)
class SchemaMetadata:
    """Technical metadata for one approved source schema."""

    name: str
    relations: tuple[RelationMetadata, ...]
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class SourceSchemaSnapshot:
    """Complete approved source metadata and its stable fingerprint."""

    identity: DatabaseIdentity
    scope: tuple[str, ...]
    schemas: tuple[SchemaMetadata, ...]
    fingerprint: str
