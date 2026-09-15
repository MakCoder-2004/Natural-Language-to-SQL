# SQL Safety and Correction

The SQL validator is a deterministic backend security component. Model output,
edited SQL, and frontend validation fields are untrusted. Only a validation
result created by the backend can authorize execution.

## Statement Policy

The default form is one PostgreSQL `SELECT`. A `WITH` statement is accepted only
when its complete AST is read-only. The parser processes the complete submitted
text, so semicolons separated by whitespace or comments cannot create a hidden
second statement.

The validator rejects data-modifying statements, DDL, transaction and session
control, privilege operations, `SELECT INTO`, locking clauses, and suspicious
functions such as `pg_sleep`, advisory locks, sequence mutation, backend control,
large-object mutation, and `dblink`. The policy is intentionally conservative:
arbitrary functions are not assumed to be side-effect free.

## Source Scope

Relations and columns are resolved from the current introspected source snapshot.
The model's `tables_used` explanation is not used for authorization. Schemas
outside the configured source scope, PostgreSQL system schemas, unknown
relations, unknown columns, ambiguous relations, and ambiguous unqualified
columns are rejected. Database-qualified references are rejected, which keeps
the local index database outside the query execution target.

## Resource Limits

The source engine applies PostgreSQL `statement_timeout`. The executor fetches
only one row beyond the configured maximum to detect truncation, normalizes
values before measuring serialized result size, and stops when the byte budget
is reached. Results explicitly expose returned row count, byte size, truncation,
and stable warnings.

Timeouts are translated to a safe `query_timeout` error. Credentials, URLs,
driver exceptions, and stack traces are not returned to clients or correction
models.

## Correction

Validation failures are represented by bounded machine-readable categories. The
correction model receives only the original intent, bounded schema context, the
prior proposal, and safe validation feedback. The backend performs a new
structured generation and deterministic validation for each attempt.

At most two correction attempts are allowed. A failed third attempt cannot be
requested by the model or frontend; the workflow ends with
`correction_exhausted`.

## Exact-SQL Boundary

Before execution, the backend revalidates the exact current SQL and recomputes
its hash. Review approval is bound to that hash. Editing SQL clears the previous
validation and approval. Execution uses a backend-created authorization and an
explicit source database binding. PostgreSQL read-only permissions provide the
independent final boundary.
