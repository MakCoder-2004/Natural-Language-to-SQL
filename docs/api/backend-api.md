# Backend API

Milestone 9 exposes the deterministic query workflow through FastAPI. The
frontend communicates only with this API; it never connects directly to either
PostgreSQL database.

## Runtime Scope

Query state is stored in memory for the lifetime of one backend process. A
backend restart removes current-session query state. Durable query history is
outside the MVP API scope.

The backend creates all query IDs, pipeline IDs, SQL hashes, validation results,
approval state, database bindings, and resource limits. Client-provided status,
validation, approval, or connection fields are rejected or ignored and never
authorize execution.

## Endpoints

### `POST /api/query`

Starts a query lifecycle.

```json
{
  "question": "Which products generated the most revenue last month?",
  "execution_mode": "REVIEW"
}
```

`execution_mode` is `REVIEW` by default and may be `AUTO`.

Review Mode returns a review-ready proposal or requests clarification. Auto Mode
continues through backend validation and execution before returning a completed
result. Both modes use the same SQL safety and resource-limit checks.

### `POST /api/query/{query_id}/clarify`

Resumes a query whose status is `CLARIFICATION_REQUIRED`.

```json
{
  "clarification": "Use total completed-order revenue."
}
```

Clarification is user context. It cannot change SQL policy, execution mode,
database selection, tools, or resource limits.

### `POST /api/query/{query_id}/edit`

Submits edited SQL as untrusted input.

```json
{
  "sql": "SELECT product_name, SUM(revenue) FROM ..."
}
```

The backend clears the previous validation and approval, validates the exact
edited SQL, and returns the updated SQL Inspector. Review Mode still requires a
new approval using the returned `sql_version`.

### `POST /api/query/{query_id}/approve`

Approves the current validated Review Mode proposal.

```json
{
  "sql_version": "backend-issued SQL hash"
}
```

The version must match the exact SQL that passed backend validation. Edited or
regenerated SQL invalidates previous approval.

### `POST /api/query/{query_id}/execute`

Executes a stored approved Review Mode query. The backend revalidates the exact
current SQL immediately before execution, verifies the approval hash, and uses
only the read-only source database binding.

Auto Mode executes during `POST /api/query`; it does not require a second
client-side execute request.

### `POST /api/query/{query_id}/regenerate`

Requests another proposal while preserving the original question, query ID,
clarification context, and execution mode. Regeneration is bounded by
`MAX_REGENERATION_COUNT` and never silently executes a new Review Mode proposal.

### `GET /api/query/{query_id}`

Returns the current query state, including applicable SQL Inspector, validation,
result, grounded answer, visualization, warnings, and safe error data.

### `GET /api/health`

Reports process, configuration, source database, index database, schema-index,
read-only permission, and model configuration status without exposing secrets,
connection URLs, stack traces, or business rows.

## Query Response

Query responses contain:

- `query_id`
- `pipeline_run_id`
- `question`
- `execution_mode`
- `status`
- `clarification`
- `sql_inspector`
- `validation`
- `result`
- `answer`
- `visualization`
- `warnings`
- Safe `error` information

Unavailable lifecycle data is returned as `null`, not as fabricated values.

The result object distinguishes zero rows from truncation and includes columns,
rows, total row count, returned row count, result bytes, warnings, truncation,
and the executed SQL hash.

## Errors

Errors use this shape:

```json
{
  "error": {
    "code": "query_not_found",
    "message": "The requested query was not found in this session.",
    "details": {}
  },
  "query_id": "optional-query-id"
}
```

The API uses `422` for malformed request bodies, `404` for unknown query IDs,
`409` for lifecycle conflicts and stale approval, `503` for unavailable source
or index dependencies, `504` for query timeouts, and safe `500` responses for
unexpected failures.

Raw stack traces, driver errors, credentials, API keys, and connection URLs are
never returned to normal users.

## Security Guarantees

- Review Mode is the default and requires explicit backend approval.
- Auto Mode cannot bypass validation or resource limits.
- Every execution request revalidates exact SQL.
- Frontend validation and approval fields never authorize execution.
- SQL hashes are generated and compared by the backend.
- Writes, DDL, multi-statement SQL, disallowed identifiers, unsafe constructs,
  and resource-limit violations remain blocked by deterministic validation.
- The local schema-index database is never an execution target.
- Database credentials and model API keys remain backend-only.
