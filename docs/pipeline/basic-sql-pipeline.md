# Basic SQL Pipeline

Milestone 5 adds the first backend-only question-to-result vertical slice:

```text
question
  -> bounded schema retrieval
  -> structured SQL proposal
  -> current source-schema validation
  -> source-only execution
  -> normalized result
  -> grounded answer
  -> deterministic visualization selection
```

## Boundaries

`BasicSqlPipelineService` owns the orchestration. The SQL model proposes an
untrusted `SqlProposal`; it cannot authorize execution or choose a database
connection. `SqlValidationService` parses the exact SQL and checks its actual
relations and columns against the current source snapshot. `ReadonlySqlExecutor`
requires the passing validation result and an explicit `SourceExecutionBinding`.

The local schema-index database is used only by retrieval. Generated business SQL
is executed only through the external source database boundary.

## Result behavior

Results are normalized into column names and JSON-compatible row values. Empty
results are successful results with zero rows. Row and serialized-byte limits are
represented with `truncated` and warnings rather than silently discarded.

Answers are generated after execution and receive the executed SQL plus normalized
result data. Database values are treated as data, not instructions. Visualization
selection is deterministic and based on result shape.

## Current scope

The baseline validator permits one read-only `SELECT` and rejects writes,
schema-changing statements, transaction control, multiple statements, and
unknown source identifiers. The complete correction, approval, edited-SQL, and
public API workflows are implemented in later milestones.
