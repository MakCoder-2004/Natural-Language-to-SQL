from pathlib import Path

import pytest
from app.database.errors import SemanticMetadataError
from app.database.models import (
    DatabaseIdentity,
    ForeignKeyMetadata,
    IndexColumnMetadata,
    IndexMetadata,
    PrimaryKeyMetadata,
    RelationMetadata,
    SchemaMetadata,
    SourceColumnMetadata,
    SourceSchemaSnapshot,
    UniqueConstraintMetadata,
)
from app.models.schema_index import IndexDocument
from app.retrieval.schema_documents import SchemaDocumentBuilder
from app.retrieval.semantic_metadata import SemanticMetadataCatalog, load_semantic_metadata


def source_snapshot() -> SourceSchemaSnapshot:
    accounts = RelationMetadata(
        schema_name="Sales Data",
        name="Account Details",
        kind="table",
        columns=(
            SourceColumnMetadata("Account ID", 1, "integer", False),
            SourceColumnMetadata("Display Name", 2, "text", True, comment="A display label"),
        ),
        primary_key=PrimaryKeyMetadata("account_details_pk", ("Account ID",)),
        unique_constraints=(
            UniqueConstraintMetadata("account_details_name_uq", ("Display Name",)),
        ),
        indexes=(
            IndexMetadata(
                "account_details_name_idx",
                (IndexColumnMetadata("Display Name"),),
            ),
        ),
        comment="Technical account relation",
    )
    events = RelationMetadata(
        schema_name="Sales Data",
        name="Event Log",
        kind="table",
        columns=(
            SourceColumnMetadata("Account ID", 1, "integer", False),
            SourceColumnMetadata("Event Name", 2, "text", True),
        ),
        foreign_keys=(
            ForeignKeyMetadata(
                name="event_account_fk",
                source_columns=("Account ID",),
                target_schema="Sales Data",
                target_relation="Account Details",
                target_columns=("Account ID",),
                cardinality="many_to_one",
            ),
            ForeignKeyMetadata(
                name="event_name_account_fk",
                source_columns=("Event Name",),
                target_schema="Sales Data",
                target_relation="Account Details",
                target_columns=("Account ID",),
                cardinality="many_to_one",
            ),
        ),
    )
    return SourceSchemaSnapshot(
        identity=DatabaseIdentity("fixture", "reader"),
        scope=("Sales Data",),
        schemas=(SchemaMetadata("Sales Data", (accounts, events), "Technical schema"),),
        fingerprint="sha256:fixture",
    )


def semantic_metadata(tmp_path: Path) -> SemanticMetadataCatalog:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Sales Data
    description: Reporting data for account activity.
    relations:
      - name: Account Details
        description: One row per reporting account.
        columns:
          - name: Account ID
            description: Stable reporting account identifier.
      - name: Event Log
        relationships:
          - name: event_account_fk
            source_columns: [Account ID]
            target:
              schema: Sales Data
              relation: Account Details
              columns: [Account ID]
            description: Each event belongs to one account.
            question_types: [activity by account]
        concepts:
          - name: Event activity
            kind: metric
            description: Count of recorded events.
            columns: [Event Name]
""",
        encoding="utf-8",
    )
    return load_semantic_metadata(metadata_file)


def test_builder_emits_rich_deterministic_documents(tmp_path: Path) -> None:
    snapshot = source_snapshot()
    catalog = semantic_metadata(tmp_path)
    builder = SchemaDocumentBuilder()

    first = builder.build(snapshot, catalog)
    second = builder.build(snapshot, catalog)

    assert first == second
    assert {document.category for document in first.documents} == {
        "table",
        "column",
        "relationship",
        "semantic_concept",
    }
    assert len(first.documents) == 9
    assert len({document.document_key for document in first.documents}) == len(first.documents)
    assert all(document.source_fingerprint == "sha256:fixture" for document in first.documents)
    assert all(document.document_version == "schema-document-v1" for document in first.documents)
    assert all(document.content_digest.startswith("sha256:") for document in first.documents)
    assert first.stale_semantic_references == ()

    table = _find(first.documents, "table", '"Sales Data"."Account Details"')
    assert "One row per reporting account." in table.content
    assert 'Primary key: "Account ID"' in table.content
    assert "Unique constraint (account_details_name_uq)" in table.content

    column = _find(first.documents, "column", '"Sales Data"."Account Details"."Account ID"')
    assert "Stable reporting account identifier." in column.content
    assert "Constraint roles: primary_key" in column.content

    relationship = _find(first.documents, "relationship", "Event Log")
    assert "Each event belongs to one account." in relationship.content
    assert "Relevant question types: activity by account" in relationship.content

    concept = _find(first.documents, "semantic_concept", "Event activity")
    assert "Count of recorded events." in concept.content


def test_builder_uses_technical_description_when_semantic_description_is_missing(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Sales Data
    relations:
      - name: Account Details
""",
        encoding="utf-8",
    )

    result = SchemaDocumentBuilder().build(source_snapshot(), load_semantic_metadata(metadata_file))

    table = _find(result.documents, "table", '"Sales Data"."Account Details"')
    assert "Technical account relation" in table.content


def test_builder_reports_stale_metadata_without_creating_documents(tmp_path: Path) -> None:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Sales Data
    relations:
      - name: Missing Relation
        description: This must not become a document.
""",
        encoding="utf-8",
    )

    result = SchemaDocumentBuilder().build(source_snapshot(), load_semantic_metadata(metadata_file))

    assert result.stale_semantic_references == ("relation:Sales Data.Missing Relation",)
    assert all("Missing Relation" not in document.content for document in result.documents)


def test_builder_can_fail_on_stale_metadata(tmp_path: Path) -> None:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Missing Schema
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticMetadataError):
        SchemaDocumentBuilder(strict_semantic_metadata=True).build(
            source_snapshot(), load_semantic_metadata(metadata_file)
        )


def _find(documents: tuple[IndexDocument, ...], category: str, identifier: str) -> IndexDocument:
    for document in documents:
        if document.category == category and identifier in document.qualified_identifier:
            return document
    raise AssertionError(f"No {category} document found for {identifier}")
