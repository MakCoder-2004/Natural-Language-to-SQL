"""Deterministic compact schema-context rendering."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.retrieval import RetrievedRelationship, RetrievedTable


class SchemaContextBuilder:
    """Render selected schema data without falling back to the full index."""

    def build(
        self,
        *,
        index_fingerprint: str,
        tables: Sequence[RetrievedTable],
        relationships: Sequence[RetrievedRelationship],
        semantic_definitions: Sequence[tuple[str, str, str]],
        max_documents: int,
        max_characters: int,
    ) -> str:
        if max_documents <= 0 or max_characters <= 0:
            raise ValueError("Schema context limits must be positive.")
        entries: list[tuple[str, bool]] = [(f"Source fingerprint: {index_fingerprint}", False)]
        required_column_entries: list[tuple[str, bool]] = []
        optional_column_entries: list[tuple[str, bool]] = []
        for table in tables:
            identifier = _qualified_relation(table.schema_name, table.relation_name)
            entries.append((f"Table: {identifier}", True))
            if table.relation_kind:
                entries.append((f"Kind: {table.relation_kind}", False))
            if table.description:
                entries.append((f"Description: {table.description}", False))
            for column in table.columns:
                details = f"- {_quote(column.column_name)}"
                if column.data_type:
                    details += f" ({column.data_type})"
                if column.nullable is not None:
                    details += ", nullable" if column.nullable else ", not nullable"
                if column.roles:
                    details += f" [{', '.join(column.roles)}]"
                if column.description:
                    details += f" - {column.description}"
                entries_for_column = (
                    required_column_entries if column.required else optional_column_entries
                )
                entries_for_column.append((f"Column: {details}", True))

        for relationship in relationships:
            source = _qualified_relation(
                relationship.source_schema_name, relationship.source_relation_name
            )
            target = _qualified_relation(
                relationship.target_schema_name, relationship.target_relation_name
            )
            line = (
                f"Relationship: {source}({_join(relationship.source_columns)}) -> "
                f"{target}({_join(relationship.target_columns)})"
            )
            if relationship.cardinality:
                line += f", {relationship.cardinality}"
            entries.append((line, True))
            if relationship.description:
                entries.append((f"Meaning: {relationship.description}", False))

        entries.extend(required_column_entries)
        for relation_key, name, description in semantic_definitions:
            entries.append((f"Definition ({relation_key}): {name} - {description}", True))
        entries.extend(optional_column_entries)

        lines: list[str] = []
        used = 0
        document_count = 0
        for line, counts_as_document in entries:
            if counts_as_document and document_count >= max_documents:
                continue
            separator = 1 if lines else 0
            if used + separator + len(line) <= max_characters:
                lines.append(line)
                used += separator + len(line)
                if counts_as_document:
                    document_count += 1
        return "\n".join(lines)


def _qualified_relation(schema_name: str, relation_name: str) -> str:
    return f"{_quote(schema_name)}.{_quote(relation_name)}"


def _quote(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _join(values: Sequence[str]) -> str:
    return ", ".join(_quote(value) for value in values)
