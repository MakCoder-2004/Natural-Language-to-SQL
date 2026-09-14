# Foundation Security Boundaries

## Secrets

Source and index database URLs and the OpenRouter API key are backend-only
settings. `.env.example` contains placeholders only, and `.gitignore` excludes
real `.env` files. Docker build contexts exclude local environment files.

Pydantic stores connection URLs and API keys as masked secret values. Startup
logs and health responses report configuration field names and safe statuses,
never secret values or complete connection URLs.

## Database Separation

The external source database is not represented by a local Compose container.
The local pgvector service is only for future schema-index data. No source
business migrations, seed scripts, or fixed business tables are present.

Future query execution must receive an explicit source-database dependency and
must remain behind deterministic SQL validation and the source database's
read-only role. Milestone 2 verifies the source role from PostgreSQL privilege
metadata without issuing writes or DDL probes against the external database.
The source execution binding rejects index database handles.

The required source role should have only `CONNECT`, schema `USAGE`, and
`SELECT` on the configured scope. The verifier rejects elevated role/database
privileges, schema `CREATE`, source-object ownership, and mutation privileges on
approved relations. Database administrators remain responsible for privileges
outside the configured scope.

Technical comments, defaults, and other catalog text are untrusted metadata.
They are collected as data for later document generation and are not interpreted
as instructions.

## Untrusted Inputs

Frontend values and future model output are not authorization decisions. The
health endpoint does not accept connection details from either client input or
model output. Later milestones must preserve backend validation, approval, and
exact-SQL checks at every execution boundary.

Connection failures and permission failures are mapped to safe application
categories. Internal causes may be retained for diagnostics, but credentials,
connection URLs, passwords, and raw database exception details are not returned
to clients.
