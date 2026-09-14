# Schema Metadata

This directory contains version-controlled semantic metadata for dynamically
discovered source database objects. It must not contain copied business rows or
a fixed production business schema.

## Format

Metadata files use version `1` and preserve source identifiers exactly. Use
structured `schema`, `relation`, and `column` fields for relationship targets;
do not encode identifiers by splitting strings on periods.

```yaml
metadata_version: 1
schemas:
  - name: <source-schema>
    description: <optional schema meaning>
    relations:
      - name: <source-relation>
        kind: table
        description: <optional relation meaning>
        columns:
          - name: <source-column>
            description: <optional column meaning>
        relationships:
          - name: <foreign-key-name>
            source_columns: [<source-column>]
            target:
              schema: <target-schema>
              relation: <target-relation>
              columns: [<target-column>]
            description: <optional relationship meaning>
            question_types: [<optional question type>]
        concepts:
          - name: <concept-name>
            kind: metric
            description: <concept meaning>
            columns: [<source-column>]
```

Technical metadata remains authoritative. Missing semantic metadata does not
prevent indexing. References to removed or renamed source objects are reported
as stale; non-strict indexing skips them, while `STRICT_SEMANTIC_METADATA=true`
fails the run safely.
