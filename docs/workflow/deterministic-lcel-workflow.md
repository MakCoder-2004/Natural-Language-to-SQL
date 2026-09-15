# Deterministic LCEL Workflow

Milestone 6 introduces `DeterministicQueryWorkflow` in
`backend/app/workflow/graph.py`. The workflow composes LCEL runnable nodes, but
the application owns every security-sensitive decision.

## State Lifecycle

The workflow uses immutable `QueryWorkflowState` values and the transition table
in `backend/app/workflow/transitions.py`:

```text
RECEIVED -> ANALYZING
ANALYZING -> CLARIFICATION_REQUIRED | SCHEMA_RETRIEVED | FAILED
SCHEMA_RETRIEVED -> SQL_GENERATED
SQL_GENERATED -> VALIDATING
VALIDATING -> SQL_CORRECTION | READY_FOR_REVIEW | EXECUTING | FAILED
SQL_CORRECTION -> SQL_GENERATED | FAILED
READY_FOR_REVIEW -> EDITED | APPROVED | EXECUTING
EDITED -> VALIDATING
APPROVED -> EXECUTING
EXECUTING -> EXECUTED | FAILED
EXECUTED -> ANSWER_GENERATED
ANSWER_GENERATED -> COMPLETED | FAILED
```

Every transition is checked centrally. Nodes return new state values rather than
mutating shared workflow state. Clarification states contain no SQL proposal or
validation result, and execution requires a passing validation bound to the
exact SQL hash.

## Routing

Question analysis is a structured LCEL model call. It classifies a question as
`ANSWERABLE`, `CLARIFICATION_REQUIRED`, `IMPOSSIBLE`, or `UNSUPPORTED`.

- `CLARIFICATION_REQUIRED` stops before retrieval and SQL generation.
- `IMPOSSIBLE` and `UNSUPPORTED` produce safe failed states.
- `ANSWERABLE` proceeds through bounded retrieval and SQL generation.
- Validation failures enter an application-controlled correction loop.
- Correction attempts cannot exceed `max_correction_retries`.

Review Mode stops at `READY_FOR_REVIEW`. Auto Mode uses the same validation and
execution gates but may proceed without an approval action.

Before every execution, the workflow revalidates the exact SQL, compares its
hash with the current authorized version, checks the source schema fingerprint,
and creates a source-only execution binding.
