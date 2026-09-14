from app.models.retrieval import (
    RetrievedColumn,
    RetrievedRelationship,
    RetrievedTable,
)
from app.retrieval.context import SchemaContextBuilder


def test_context_builder_includes_quoted_identifiers_and_relationship_columns() -> None:
    table = RetrievedTable(
        schema_name="Sales Data",
        relation_name="Event Log",
        relation_kind="table",
        description="Recorded activity",
        score=1.0,
        direct=True,
        evidence_document_keys=("table:events",),
        columns=(
            RetrievedColumn(
                schema_name="Sales Data",
                relation_name="Event Log",
                column_name="Account ID",
                data_type="integer",
                nullable=False,
                description="Owning account",
                roles=("foreign_key",),
                score=1.0,
                required=True,
            ),
        ),
    )
    relationship = RetrievedRelationship(
        source_schema_name="Sales Data",
        source_relation_name="Event Log",
        source_columns=("Account ID",),
        target_schema_name="Sales Data",
        target_relation_name="Account Details",
        target_columns=("Account ID",),
        cardinality="many_to_one",
        description="Each event belongs to one account.",
        score=1.0,
        expanded=True,
        document_key="relationship:event-account",
    )

    result = SchemaContextBuilder().build(
        index_fingerprint="sha256:test",
        tables=(table,),
        relationships=(relationship,),
        semantic_definitions=(("Sales Data.Event Log", "Event activity", "Count of events"),),
        max_documents=10,
        max_characters=2000,
    )

    assert 'Table: "Sales Data"."Event Log"' in result
    assert 'Column: - "Account ID" (integer), not nullable [foreign_key]' in result
    assert (
        'Relationship: "Sales Data"."Event Log"("Account ID") -> '
        '"Sales Data"."Account Details"("Account ID")'
    ) in result
    assert "Each event belongs to one account." in result
    assert "Event activity - Count of events" in result


def test_context_builder_enforces_document_and_character_bounds() -> None:
    tables = tuple(
        RetrievedTable(
            schema_name="analytics",
            relation_name=f"table_{index}",
            relation_kind="table",
            description="A table",
            score=1.0,
            direct=True,
            evidence_document_keys=(),
            columns=(),
        )
        for index in range(5)
    )

    result = SchemaContextBuilder().build(
        index_fingerprint="sha256:test",
        tables=tables,
        relationships=(),
        semantic_definitions=(),
        max_documents=2,
        max_characters=80,
    )

    assert len(result) <= 80
    assert result.count("Table:") <= 2
