# Controlled Agent Boundaries

The controlled agent is implemented in `backend/app/agent/` and is a bounded
application component, not an unrestricted database agent.

## Approved Tools

Only these application-owned tools are exposed:

- `get_relevant_schema` reads bounded schema documents from the local index.
- `generate_sql` proposes structured SQL from the retrieved context.
- `execute_readonly_sql` executes only a backend-created authorization capability.

Tool input schemas reject extra fields. They do not accept credentials, URLs,
database names, connection objects, arbitrary SQL targets, or retry settings.

## Database Separation

The retrieval tool receives an application-owned retrieval service connected to
the local schema index. The execution tool receives an application-owned
`SourceExecutionBinding`. `SourceExecutionBinding` rejects index database
handles, and the model cannot construct or replace either binding.

## Execution Authorization

`ExecutionAuthorization` is created only after deterministic validation and the
appropriate Review or Auto Mode gate. It contains the exact validated SQL,
SQL hash, source fingerprint, validation result, source binding, and configured
resource limits.

The model cannot create this capability. Review Mode requires an approval hash
matching the current validated SQL. Edited SQL clears the previous validation
and must pass validation again.

## State Isolation

The agent receives bounded values and tool wrappers, not the mutable workflow
state. Tools return values to the workflow; only the workflow applies state
transitions, increments correction counts, and decides whether execution is
permitted.
