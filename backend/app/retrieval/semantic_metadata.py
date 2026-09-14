"""Versioned, application-controlled semantic metadata for source objects."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.database.errors import SemanticMetadataError
from app.database.models import ForeignKeyMetadata, SourceSchemaSnapshot

SemanticConceptKind = Literal["metric", "dimension", "status", "definition", "other"]


class _MetadataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class SemanticTarget(_MetadataModel):
    """Exact target of a semantic relationship."""

    schema_name: str = Field(alias="schema", min_length=1)
    relation: str = Field(min_length=1)
    columns: tuple[str, ...] = Field(min_length=1)


class SemanticColumn(_MetadataModel):
    """Optional semantic description for one discovered column."""

    name: str = Field(min_length=1)
    description: str | None = None


class SemanticRelationship(_MetadataModel):
    """Optional semantic description for one discovered foreign key."""

    name: str | None = None
    source_columns: tuple[str, ...] = Field(min_length=1)
    target: SemanticTarget
    description: str | None = None
    question_types: tuple[str, ...] = ()


class SemanticConcept(_MetadataModel):
    """A business concept anchored to one discovered relation."""

    name: str = Field(min_length=1)
    kind: SemanticConceptKind = "other"
    description: str = Field(min_length=1)
    columns: tuple[str, ...] = ()


class SemanticRelation(_MetadataModel):
    """Optional semantic metadata for one discovered relation."""

    name: str = Field(min_length=1)
    kind: Literal["table", "view", "materialized_view"] | None = None
    description: str | None = None
    columns: tuple[SemanticColumn, ...] = ()
    relationships: tuple[SemanticRelationship, ...] = ()
    concepts: tuple[SemanticConcept, ...] = ()


class SemanticSchema(_MetadataModel):
    """Optional semantic metadata for one discovered schema."""

    name: str = Field(min_length=1)
    description: str | None = None
    relations: tuple[SemanticRelation, ...] = ()


class SemanticMetadataDocument(_MetadataModel):
    """Versioned semantic metadata document."""

    metadata_version: Literal[1]
    schemas: tuple[SemanticSchema, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticMetadataCatalog:
    """Loaded metadata plus a stable digest of its canonical contents."""

    document: SemanticMetadataDocument
    digest: str
    source_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticMetadataDiagnostics:
    """Non-fatal metadata references that do not match the source snapshot."""

    stale_references: tuple[str, ...]


def load_semantic_metadata(path: str | Path) -> SemanticMetadataCatalog:
    """Load one metadata file or all YAML files in a metadata directory."""

    metadata_path = Path(path)
    files = _metadata_files(metadata_path)
    if not files:
        document = SemanticMetadataDocument(metadata_version=1)
        return SemanticMetadataCatalog(document, _metadata_digest(document), ())

    documents = tuple(_load_file(file_path) for file_path in files)
    if any(document.metadata_version != 1 for document in documents):
        raise SemanticMetadataError("Semantic metadata uses an unsupported version.")
    schemas: list[SemanticSchema] = []
    seen_schemas: set[str] = set()
    for document in documents:
        for schema in document.schemas:
            if schema.name in seen_schemas:
                raise SemanticMetadataError("Semantic metadata contains a duplicate schema.")
            seen_schemas.add(schema.name)
            schemas.append(schema)
    combined = SemanticMetadataDocument(metadata_version=1, schemas=tuple(schemas))
    return SemanticMetadataCatalog(
        combined, _metadata_digest(combined), tuple(str(file_path) for file_path in files)
    )


def diagnose_semantic_metadata(
    catalog: SemanticMetadataCatalog, snapshot: SourceSchemaSnapshot
) -> SemanticMetadataDiagnostics:
    """Find semantic references that cannot be grounded in technical metadata."""

    schemas = {schema.name: schema for schema in snapshot.schemas}
    stale: list[str] = []
    for semantic_schema in catalog.document.schemas:
        technical_schema = schemas.get(semantic_schema.name)
        if technical_schema is None:
            stale.append(f"schema:{semantic_schema.name}")
            continue
        relations = {relation.name: relation for relation in technical_schema.relations}
        for semantic_relation in semantic_schema.relations:
            technical_relation = relations.get(semantic_relation.name)
            relation_key = f"relation:{semantic_schema.name}.{semantic_relation.name}"
            if technical_relation is None:
                stale.append(relation_key)
                continue
            columns = {column.name for column in technical_relation.columns}
            for semantic_column in semantic_relation.columns:
                if semantic_column.name not in columns:
                    stale.append(f"{relation_key}.column:{semantic_column.name}")
            for concept in semantic_relation.concepts:
                for column_name in concept.columns:
                    if column_name not in columns:
                        stale.append(f"{relation_key}.concept:{concept.name}.column:{column_name}")
            for relationship in semantic_relation.relationships:
                if not _matches_foreign_key(relationship, technical_relation.foreign_keys):
                    stale.append(f"{relation_key}.relationship:{_relationship_label(relationship)}")
    return SemanticMetadataDiagnostics(tuple(sorted(set(stale))))


def _metadata_files(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,)
    if not path.exists():
        return ()
    if not path.is_dir():
        raise SemanticMetadataError("The semantic metadata path is not a file or directory.")
    return tuple(sorted((*path.glob("*.yaml"), *path.glob("*.yml"))))


def _load_file(path: Path) -> SemanticMetadataDocument:
    try:
        with path.open("r", encoding="utf-8") as metadata_file:
            raw_document = yaml.safe_load(metadata_file) or {}
        return SemanticMetadataDocument.model_validate(raw_document)
    except (OSError, yaml.YAMLError, TypeError, ValueError) as exc:
        raise SemanticMetadataError("Semantic metadata could not be loaded.") from exc


def _metadata_digest(document: SemanticMetadataDocument) -> str:
    canonical = json.dumps(
        document.model_dump(mode="json", by_alias=True),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _matches_foreign_key(
    semantic_relationship: SemanticRelationship, foreign_keys: tuple[ForeignKeyMetadata, ...]
) -> bool:
    for foreign_key in foreign_keys:
        if (
            semantic_relationship.name is not None
            and foreign_key.name != semantic_relationship.name
        ):
            continue
        if tuple(semantic_relationship.source_columns) != foreign_key.source_columns:
            continue
        target = semantic_relationship.target
        if (
            target.schema_name != foreign_key.target_schema
            or target.relation != foreign_key.target_relation
        ):
            continue
        if tuple(target.columns) == foreign_key.target_columns:
            return True
    return False


def _relationship_label(relationship: SemanticRelationship) -> str:
    name = relationship.name or "unnamed"
    return name
