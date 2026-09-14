from pathlib import Path

import pytest
from app.database.errors import SemanticMetadataError
from app.database.models import (
    DatabaseIdentity,
    ForeignKeyMetadata,
    RelationMetadata,
    SchemaMetadata,
    SourceColumnMetadata,
    SourceSchemaSnapshot,
)
from app.retrieval.semantic_metadata import (
    diagnose_semantic_metadata,
    load_semantic_metadata,
)


def source_snapshot() -> SourceSchemaSnapshot:
    accounts = RelationMetadata(
        schema_name="Sales Data",
        name="Account Details",
        kind="table",
        columns=(
            SourceColumnMetadata("Account ID", 1, "integer", False),
            SourceColumnMetadata("Display Name", 2, "text", True),
        ),
    )
    events = RelationMetadata(
        schema_name="Sales Data",
        name="Event Log",
        kind="table",
        columns=(SourceColumnMetadata("Account ID", 1, "integer", False),),
        foreign_keys=(
            ForeignKeyMetadata(
                name="event_account_fk",
                source_columns=("Account ID",),
                target_schema="Sales Data",
                target_relation="Account Details",
                target_columns=("Account ID",),
            ),
        ),
    )
    return SourceSchemaSnapshot(
        identity=DatabaseIdentity("fixture", "reader"),
        scope=("Sales Data",),
        schemas=(SchemaMetadata("Sales Data", (accounts, events)),),
        fingerprint="sha256:fixture",
    )


def test_load_semantic_metadata_preserves_arbitrary_identifiers(tmp_path: Path) -> None:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Sales Data
    description: A reporting namespace.
    relations:
      - name: Account Details
        description: Account-level reporting attributes.
        columns:
          - name: Account ID
            description: The stable account key.
        concepts:
          - name: Active account
            kind: status
            description: Whether an account is currently active.
            columns: [Account ID]
""",
        encoding="utf-8",
    )

    catalog = load_semantic_metadata(metadata_file)

    schema = catalog.document.schemas[0]
    assert schema.name == "Sales Data"
    assert schema.relations[0].name == "Account Details"
    assert schema.relations[0].columns[0].name == "Account ID"
    assert catalog.digest.startswith("sha256:")


def test_missing_metadata_directory_returns_empty_catalog(tmp_path: Path) -> None:
    catalog = load_semantic_metadata(tmp_path / "missing")

    assert catalog.document.metadata_version == 1
    assert catalog.document.schemas == ()
    assert catalog.source_files == ()


def test_duplicate_schema_metadata_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "one.yaml").write_text(
        "metadata_version: 1\nschemas:\n  - name: Sales Data\n", encoding="utf-8"
    )
    (tmp_path / "two.yaml").write_text(
        "metadata_version: 1\nschemas:\n  - name: Sales Data\n", encoding="utf-8"
    )

    with pytest.raises(SemanticMetadataError):
        load_semantic_metadata(tmp_path)


def test_diagnostics_report_stale_nested_references(tmp_path: Path) -> None:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Sales Data
    relations:
      - name: Account Details
        columns:
          - name: Missing Column
        concepts:
          - name: Missing concept anchor
            description: A stale concept.
            columns: [Missing Column]
      - name: Missing Relation
      - name: Event Log
        relationships:
          - name: missing_fk
            source_columns: [Account ID]
            target:
              schema: Sales Data
              relation: Account Details
              columns: [Account ID]
""",
        encoding="utf-8",
    )

    diagnostics = diagnose_semantic_metadata(
        load_semantic_metadata(metadata_file), source_snapshot()
    )

    assert (
        "relation:Sales Data.Account Details.column:Missing Column" in diagnostics.stale_references
    )
    assert (
        "relation:Sales Data.Account Details.concept:Missing concept anchor.column:Missing Column"
        in diagnostics.stale_references
    )
    assert "relation:Sales Data.Missing Relation" in diagnostics.stale_references
    assert "relation:Sales Data.Event Log.relationship:missing_fk" in diagnostics.stale_references


def test_diagnostics_accept_exact_foreign_key_reference(tmp_path: Path) -> None:
    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text(
        """
metadata_version: 1
schemas:
  - name: Sales Data
    relations:
      - name: Event Log
        relationships:
          - name: event_account_fk
            source_columns: [Account ID]
            target:
              schema: Sales Data
              relation: Account Details
              columns: [Account ID]
""",
        encoding="utf-8",
    )

    diagnostics = diagnose_semantic_metadata(
        load_semantic_metadata(metadata_file), source_snapshot()
    )

    assert diagnostics.stale_references == ()
