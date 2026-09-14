from dataclasses import replace

from app.database.models import (
    DatabaseIdentity,
    RelationMetadata,
    SchemaMetadata,
    SourceColumnMetadata,
)
from app.database.source_introspection import source_schema_fingerprint


def snapshot_parts() -> tuple[SchemaMetadata, ...]:
    relation = RelationMetadata(
        schema_name="analytics",
        name="events",
        kind="table",
        columns=(
            SourceColumnMetadata(
                name="event_id",
                ordinal_position=1,
                data_type="INTEGER",
                nullable=False,
            ),
        ),
    )
    return (SchemaMetadata(name="analytics", relations=(relation,)),)


def test_fingerprint_is_stable_for_equal_metadata() -> None:
    first = source_schema_fingerprint(("analytics",), snapshot_parts())
    second = source_schema_fingerprint(("analytics",), snapshot_parts())

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64


def test_fingerprint_changes_when_document_relevant_metadata_changes() -> None:
    original = snapshot_parts()
    changed_relation = replace(
        original[0].relations[0],
        columns=(replace(original[0].relations[0].columns[0], nullable=True),),
    )
    changed = (replace(original[0], relations=(changed_relation,)),)

    assert source_schema_fingerprint(("analytics",), original) != source_schema_fingerprint(
        ("analytics",), changed
    )


def test_fingerprint_excludes_database_identity() -> None:
    metadata = snapshot_parts()
    first_identity = DatabaseIdentity("database_a", "reader")
    second_identity = DatabaseIdentity("database_b", "reader")

    assert first_identity != second_identity
    assert source_schema_fingerprint(("analytics",), metadata) == source_schema_fingerprint(
        ("analytics",), metadata
    )
