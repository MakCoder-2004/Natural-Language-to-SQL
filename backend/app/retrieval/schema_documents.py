"""Deterministic technical and semantic schema document construction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from app.database.errors import SemanticMetadataError
from app.database.models import (
    ForeignKeyMetadata,
    IndexMetadata,
    RelationMetadata,
    SchemaMetadata,
    SourceColumnMetadata,
    SourceSchemaSnapshot,
)
from app.models.schema_index import DocumentCategory, IndexDocument, SchemaDocumentBuildResult
from app.retrieval.semantic_metadata import (
    SemanticMetadataCatalog,
    SemanticRelation,
    SemanticRelationship,
    diagnose_semantic_metadata,
)

DEFAULT_DOCUMENT_VERSION = "schema-document-v1"


class SchemaDocumentBuilder:
    """Build rich documents without inventing source objects."""

    def __init__(
        self,
        *,
        document_version: str = DEFAULT_DOCUMENT_VERSION,
        strict_semantic_metadata: bool = False,
    ) -> None:
        self.document_version = document_version
        self.strict_semantic_metadata = strict_semantic_metadata

    def build(
        self, snapshot: SourceSchemaSnapshot, catalog: SemanticMetadataCatalog
    ) -> SchemaDocumentBuildResult:
        """Build a stable complete document set from one source snapshot."""

        diagnostics = diagnose_semantic_metadata(catalog, snapshot)
        if self.strict_semantic_metadata and diagnostics.stale_references:
            raise SemanticMetadataError("Semantic metadata contains stale source references.")

        semantic_schemas = {schema.name: schema for schema in catalog.document.schemas}
        documents: list[IndexDocument] = []
        source_key = source_index_key(snapshot)
        for schema in sorted(snapshot.schemas, key=lambda item: item.name):
            semantic_schema = semantic_schemas.get(schema.name)
            semantic_relations = (
                {relation.name: relation for relation in semantic_schema.relations}
                if semantic_schema is not None
                else {}
            )
            for relation in sorted(schema.relations, key=lambda item: (item.name, item.kind)):
                semantic_relation = semantic_relations.get(relation.name)
                documents.append(
                    self._table_document(
                        snapshot,
                        source_key,
                        schema,
                        relation,
                        semantic_schema.description if semantic_schema else None,
                        semantic_relation,
                        catalog.digest,
                    )
                )
                documents.extend(
                    self._column_documents(
                        snapshot,
                        source_key,
                        relation,
                        semantic_relation,
                        catalog.digest,
                    )
                )
                documents.extend(
                    self._relationship_documents(
                        snapshot,
                        source_key,
                        relation,
                        semantic_relation,
                        catalog.digest,
                    )
                )
                documents.extend(
                    self._concept_documents(
                        snapshot,
                        source_key,
                        relation,
                        semantic_relation,
                        catalog.digest,
                    )
                )
        documents.sort(key=lambda document: (document.category, document.qualified_identifier))
        return SchemaDocumentBuildResult(
            documents=tuple(documents),
            stale_semantic_references=diagnostics.stale_references,
            source_key=source_key,
            source_fingerprint=snapshot.fingerprint,
            semantic_metadata_digest=catalog.digest,
            document_version=self.document_version,
        )

    def _table_document(
        self,
        snapshot: SourceSchemaSnapshot,
        source_key: str,
        schema: SchemaMetadata,
        relation: RelationMetadata,
        schema_description: str | None,
        semantic_relation: SemanticRelation | None,
        semantic_digest: str,
    ) -> IndexDocument:
        semantic_description = semantic_relation.description if semantic_relation else None
        description = semantic_description or relation.comment or schema_description
        qualified = _qualified_relation(relation.schema_name, relation.name)
        lines = [f"Relation: {qualified}", f"Relation kind: {relation.kind}"]
        _append_optional(lines, "Description", description)
        lines.append("Columns:")
        semantic_columns = _semantic_columns(semantic_relation)
        for column in relation.columns:
            column_description = semantic_columns.get(column.name) or column.comment
            details = (
                f"{_quote_identifier(column.name)} ({column.data_type}, {_nullability(column)})"
            )
            if column_description:
                details += f" - {column_description}"
            lines.append(f"- {details}")
        _append_constraint_lines(lines, relation)
        if relation.foreign_keys:
            lines.append("Relationships:")
            for foreign_key in relation.foreign_keys:
                lines.append(f"- {_relationship_text(relation, foreign_key)}")
        if relation.indexes:
            lines.append("Indexes:")
            for index in relation.indexes:
                lines.append(f"- {_index_text(index)}")
        if semantic_relation and semantic_relation.concepts:
            lines.append("Analytical concepts:")
            for concept in semantic_relation.concepts:
                lines.append(f"- {concept.name}: {concept.description}")
        metadata = {
            "relation_kind": relation.kind,
            "schema_description": schema_description,
            "technical_description": relation.comment,
            "semantic_description": semantic_description,
            "column_names": [column.name for column in relation.columns],
            "primary_key": list(relation.primary_key.columns) if relation.primary_key else [],
            "foreign_key_count": len(relation.foreign_keys),
            "index_names": [index.name for index in relation.indexes],
        }
        return self._document(
            snapshot,
            source_key,
            "table",
            relation.schema_name,
            relation.name,
            None,
            None,
            None,
            (),
            qualified,
            "\n".join(lines),
            metadata,
            semantic_digest,
        )

    def _column_documents(
        self,
        snapshot: SourceSchemaSnapshot,
        source_key: str,
        relation: RelationMetadata,
        semantic_relation: SemanticRelation | None,
        semantic_digest: str,
    ) -> tuple[IndexDocument, ...]:
        semantic_columns = _semantic_column_models(semantic_relation)
        documents = []
        for column in relation.columns:
            semantic_column = semantic_columns.get(column.name)
            qualified = _qualified_column(relation.schema_name, relation.name, column.name)
            roles = _column_roles(relation, column.name)
            lines = [
                f"Column: {qualified}",
                f"Relation kind: {relation.kind}",
                f"Type: {column.data_type}",
                f"Nullability: {_nullability(column)}",
            ]
            _append_optional(
                lines, "Description", semantic_column.description if semantic_column else None
            )
            if column.comment and (semantic_column is None or semantic_column.description is None):
                _append_optional(lines, "Database comment", column.comment)
            _append_optional(lines, "Default", column.default)
            if roles:
                lines.append(f"Constraint roles: {', '.join(roles)}")
            documents.append(
                self._document(
                    snapshot,
                    source_key,
                    "column",
                    relation.schema_name,
                    relation.name,
                    column.name,
                    None,
                    None,
                    (),
                    qualified,
                    "\n".join(lines),
                    {
                        "relation_kind": relation.kind,
                        "data_type": column.data_type,
                        "nullable": column.nullable,
                        "default": column.default,
                        "technical_description": column.comment,
                        "semantic_description": (
                            semantic_column.description if semantic_column else None
                        ),
                        "constraint_roles": roles,
                    },
                    semantic_digest,
                )
            )
        return tuple(documents)

    def _relationship_documents(
        self,
        snapshot: SourceSchemaSnapshot,
        source_key: str,
        relation: RelationMetadata,
        semantic_relation: SemanticRelation | None,
        semantic_digest: str,
    ) -> tuple[IndexDocument, ...]:
        documents = []
        for foreign_key in relation.foreign_keys:
            semantic_relationship = _semantic_relationship(foreign_key, semantic_relation)
            source = _qualified_relation(relation.schema_name, relation.name)
            target = _qualified_relation(foreign_key.target_schema, foreign_key.target_relation)
            qualified = f"{source} -> {target}"
            lines = [
                f"Relationship: {qualified}",
                (
                    "Source columns: "
                    f"{', '.join(_quote_identifier(name) for name in foreign_key.source_columns)}"
                ),
                (
                    "Target columns: "
                    f"{', '.join(_quote_identifier(name) for name in foreign_key.target_columns)}"
                ),
                f"Direction: {source} references {target}",
                f"Cardinality: {foreign_key.cardinality}",
            ]
            _append_optional(
                lines,
                "Description",
                semantic_relationship.description if semantic_relationship else None,
            )
            _append_optional(lines, "On update", foreign_key.on_update)
            _append_optional(lines, "On delete", foreign_key.on_delete)
            if semantic_relationship and semantic_relationship.question_types:
                lines.append(
                    f"Relevant question types: {', '.join(semantic_relationship.question_types)}"
                )
            documents.append(
                self._document(
                    snapshot,
                    source_key,
                    "relationship",
                    relation.schema_name,
                    relation.name,
                    None,
                    foreign_key.target_schema,
                    foreign_key.target_relation,
                    foreign_key.target_columns,
                    qualified,
                    "\n".join(lines),
                    {
                        "constraint_name": foreign_key.name,
                        "source_columns": list(foreign_key.source_columns),
                        "target_schema": foreign_key.target_schema,
                        "target_relation": foreign_key.target_relation,
                        "target_columns": list(foreign_key.target_columns),
                        "cardinality": foreign_key.cardinality,
                        "on_update": foreign_key.on_update,
                        "on_delete": foreign_key.on_delete,
                        "semantic_description": (
                            semantic_relationship.description if semantic_relationship else None
                        ),
                        "question_types": (
                            list(semantic_relationship.question_types)
                            if semantic_relationship
                            else []
                        ),
                    },
                    semantic_digest,
                )
            )
        return tuple(documents)

    def _concept_documents(
        self,
        snapshot: SourceSchemaSnapshot,
        source_key: str,
        relation: RelationMetadata,
        semantic_relation: SemanticRelation | None,
        semantic_digest: str,
    ) -> tuple[IndexDocument, ...]:
        if semantic_relation is None:
            return ()
        documents = []
        columns = {column.name for column in relation.columns}
        for concept in semantic_relation.concepts:
            if any(column_name not in columns for column_name in concept.columns):
                continue
            qualified = _qualified_relation(relation.schema_name, relation.name)
            lines = [
                f"Semantic concept: {concept.name}",
                f"Kind: {concept.kind}",
                f"Relation: {qualified}",
                f"Description: {concept.description}",
            ]
            if concept.columns:
                lines.append(
                    f"Columns: {', '.join(_quote_identifier(name) for name in concept.columns)}"
                )
            documents.append(
                self._document(
                    snapshot,
                    source_key,
                    "semantic_concept",
                    relation.schema_name,
                    relation.name,
                    None,
                    None,
                    None,
                    (),
                    f"{qualified} :: {concept.name}",
                    "\n".join(lines),
                    {
                        "concept_name": concept.name,
                        "concept_kind": concept.kind,
                        "relation": relation.name,
                        "column_names": list(concept.columns),
                    },
                    semantic_digest,
                )
            )
        return tuple(documents)

    def _document(
        self,
        snapshot: SourceSchemaSnapshot,
        source_key: str,
        category: DocumentCategory,
        schema_name: str,
        relation_name: str | None,
        column_name: str | None,
        target_schema_name: str | None,
        target_relation_name: str | None,
        target_column_names: tuple[str, ...],
        qualified_identifier: str,
        content: str,
        metadata: dict[str, Any],
        semantic_digest: str,
    ) -> IndexDocument:
        identity = {
            "source_key": source_key,
            "category": category,
            "schema_name": schema_name,
            "relation_name": relation_name,
            "column_name": column_name,
            "target_schema_name": target_schema_name,
            "target_relation_name": target_relation_name,
            "target_column_names": list(target_column_names),
        }
        identity_bytes = _canonical_json(identity)
        document_key = f"{category}:{hashlib.sha256(identity_bytes).hexdigest()}"
        content_digest = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
        metadata_with_identity = {
            **metadata,
            "source_key": source_key,
            "category": category,
            "qualified_identifier": qualified_identifier,
            "source_fingerprint": snapshot.fingerprint,
            "semantic_metadata_digest": semantic_digest,
            "document_version": self.document_version,
            "content_digest": content_digest,
        }
        return IndexDocument(
            document_key=document_key,
            category=category,
            source_key=source_key,
            schema_name=schema_name,
            relation_name=relation_name,
            column_name=column_name,
            target_schema_name=target_schema_name,
            target_relation_name=target_relation_name,
            target_column_names=target_column_names,
            qualified_identifier=qualified_identifier,
            content=content,
            metadata=metadata_with_identity,
            source_fingerprint=snapshot.fingerprint,
            semantic_metadata_digest=semantic_digest,
            document_version=self.document_version,
            content_digest=content_digest,
        )


def source_index_key(snapshot: SourceSchemaSnapshot) -> str:
    """Return the non-secret namespace used to isolate one source index."""

    scope = ",".join(sorted(set(snapshot.scope)))
    return f"postgres:{snapshot.identity.database_name}|scope:{scope}"


def _semantic_columns(semantic_relation: SemanticRelation | None) -> dict[str, str]:
    return {
        column.name: column.description
        for column in (semantic_relation.columns if semantic_relation else ())
        if column.description
    }


def _semantic_column_models(semantic_relation: SemanticRelation | None) -> dict[str, Any]:
    return {
        column.name: column for column in (semantic_relation.columns if semantic_relation else ())
    }


def _semantic_relationship(
    foreign_key: ForeignKeyMetadata, semantic_relation: SemanticRelation | None
) -> SemanticRelationship | None:
    if semantic_relation is None:
        return None
    for relationship in semantic_relation.relationships:
        target = relationship.target
        if relationship.name is not None and relationship.name != foreign_key.name:
            continue
        if tuple(relationship.source_columns) != foreign_key.source_columns:
            continue
        if target.schema_name != foreign_key.target_schema:
            continue
        if target.relation != foreign_key.target_relation:
            continue
        if tuple(target.columns) == foreign_key.target_columns:
            return relationship
    return None


def _column_roles(relation: RelationMetadata, column_name: str) -> tuple[str, ...]:
    roles: list[str] = []
    if relation.primary_key and column_name in relation.primary_key.columns:
        roles.append("primary_key")
    if any(column_name in constraint.columns for constraint in relation.unique_constraints):
        roles.append("unique")
    if any(column_name in foreign_key.source_columns for foreign_key in relation.foreign_keys):
        roles.append("foreign_key")
    return tuple(roles)


def _append_constraint_lines(lines: list[str], relation: RelationMetadata) -> None:
    if relation.primary_key:
        lines.append(f"Primary key: {_join_identifiers(relation.primary_key.columns)}")
    for constraint in relation.unique_constraints:
        name = f" ({constraint.name})" if constraint.name else ""
        lines.append(f"Unique constraint{name}: {_join_identifiers(constraint.columns)}")


def _relationship_text(relation: RelationMetadata, foreign_key: ForeignKeyMetadata) -> str:
    source = _qualified_relation(relation.schema_name, relation.name)
    target = _qualified_relation(foreign_key.target_schema, foreign_key.target_relation)
    return (
        f"{source}({_join_identifiers(foreign_key.source_columns)}) -> "
        f"{target}({_join_identifiers(foreign_key.target_columns)}), "
        f"{foreign_key.cardinality}"
    )


def _index_text(index: IndexMetadata) -> str:
    columns = ", ".join(
        f"{_quote_identifier(column.name)} {column.sort_order} NULLS {column.nulls_order}"
        for column in index.columns
    )
    qualifier = "unique " if index.unique else ""
    return f"{qualifier}{index.name} ({columns})"


def _join_identifiers(names: Iterable[str]) -> str:
    return ", ".join(_quote_identifier(name) for name in names)


def _qualified_relation(schema_name: str, relation_name: str) -> str:
    return f"{_quote_identifier(schema_name)}.{_quote_identifier(relation_name)}"


def _qualified_column(schema_name: str, relation_name: str, column_name: str) -> str:
    return f"{_qualified_relation(schema_name, relation_name)}.{_quote_identifier(column_name)}"


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _nullability(column: SourceColumnMetadata) -> str:
    return "nullable" if column.nullable else "not nullable"


def _append_optional(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"{label}: {value}")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
