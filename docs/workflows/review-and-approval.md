# Review and Approval Workflow

Milestone 8 defines the backend-owned lifecycle between SQL proposal generation
and source-database execution. Review Mode is the default and requires an
explicit approval for the exact SQL version being executed.

## Modes

Review Mode stops at `READY_FOR_REVIEW` after deterministic validation passes.
The caller must approve the current SQL version before execution can begin.

Auto Mode can continue after the same deterministic validation and resource
checks pass. Auto Mode does not bypass source-database permissions, immediate
execution revalidation, or result limits.

## SQL Versions

The backend computes a SHA-256 hash of the exact SQL text. This hash is the SQL
version token. Approval is valid only when its hash matches the current proposal
and the current validation result.

The original generated proposal is retained separately from the current
proposal. Editing or regeneration changes the current SQL version but does not
change the original question or original proposal.

## Review Inspector

The backend-derived SQL Inspector exposes:

- Current and original SQL.
- Current SQL version hash.
- Interpretation, tables used, and assumptions.
- Validation result and blocking errors.
- Read-only status.
- Approved-source status.
- Single-statement status.
- Applied resource limits.
- Warnings.
- Approval-required, approved, and stale-approval status.

Inspector fields are informational projections of backend state. They cannot
authorize execution.

## Editing

Edited SQL is untrusted input. An edit:

1. Replaces the current proposal SQL.
2. Computes a new backend SQL version.
3. Clears validation and approval state.
4. Transitions through `EDITED` and `VALIDATING`.
5. Returns to review only after full deterministic validation passes.

The old approval cannot authorize edited SQL. Review Mode requires a new
approval for the new version.

## Regeneration

Regeneration is an explicit user action from `READY_FOR_REVIEW`. It preserves
the query ID, original question, clarification context, execution mode, and
original proposal. It clears current validation and approval, increments bounded
regeneration telemetry, generates a new proposal, and validates it again.

Regeneration never executes automatically in Review Mode. The configured
`MAX_REGENERATION_COUNT` limit prevents unbounded model calls.

## Execution Boundary

Before source execution, the backend:

- Re-introspects the source schema.
- Revalidates the exact current SQL.
- Verifies the SQL hash matches the current validated version.
- Verifies Review Mode approval when applicable.
- Creates a backend-owned execution authorization.
- Executes only through the source database binding.

Frontend validation indicators, approval fields, SQL text, and version tokens are
never trusted without backend verification. The local schema-index database is
never an execution target.

## Clarification Context

The original natural-language question remains associated with the query across
clarification, correction, editing, and regeneration. Clarification is user
context, not a security instruction, and cannot change execution mode, tool
permissions, SQL policy, or resource limits.
