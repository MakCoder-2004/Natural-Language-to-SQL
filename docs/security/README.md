# Security Documentation

Document credential handling, read-only database boundaries, validation policy,
execution gates, and untrusted input handling here.

## Runtime Source Connections

The `/settings` page supports one source database for the running local backend.
The browser sends the connection URL to FastAPI; it never connects directly to
PostgreSQL. FastAPI validates the PostgreSQL URL, introspects the approved
schema, and verifies the role's read-only privileges before saving the source
binding in process memory.

The full URL is never returned in API responses, browser storage, query history,
logs, or error messages. Disconnecting removes the active source binding, and a
backend restart clears it. The local `index-db` binding remains separate and
cannot be selected as the source.

Use a dedicated administrator-provisioned role with `CONNECT`, schema `USAGE`,
and `SELECT` only. Do not use an owner, superuser, or write-capable role. This
single-user feature is not a substitute for authentication, tenant isolation,
or encrypted multi-user secret storage.
