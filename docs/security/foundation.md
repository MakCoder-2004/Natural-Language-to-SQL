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
business migrations, seed scripts, or fixed business tables are present. The
indexing command creates the `vector` extension and index tables only in the
separate local index database.

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

Semantic metadata is version-controlled application input. It is matched only
to exact discovered source identifiers. Stale references are reported and never
create fictional source objects. Embedding requests use backend-only
OpenRouter credentials, and index failures expose only safe error categories.

## Untrusted Inputs

Frontend values and future model output are not authorization decisions. The
health endpoint does not accept connection details from either client input or
model output. Later milestones must preserve backend validation, approval, and
exact-SQL checks at every execution boundary.

Connection failures and permission failures are mapped to safe application
categories. Internal causes may be retained for diagnostics, but credentials,
connection URLs, passwords, and raw database exception details are not returned
to clients.

## Retrieval Boundaries

Hybrid retrieval reads only promoted schema documents and embeddings from the
separate local index database. The source database is used only for bounded
technical metadata readiness checks; source business rows are not read or
embedded by retrieval.

The vector and keyword candidate counts, table/column limits, relationship hop
limit, and context size are backend-owned settings. Retrieval filters every
candidate by the trusted source key and current source fingerprint, rejects
stale or failed indexes, and never accepts a source scope or unrestricted
`top_k` from a model or frontend.

Foreign-key expansion is limited to immediate relationships of high-confidence
selected tables. Direction and join columns come from indexed technical
metadata, not model-generated names. Retrieved comments and semantic
descriptions remain untrusted data and cannot change tool permissions,
workflow state, database selection, or SQL policy.

Retrieval diagnostics contain counts, safe fingerprints, limits, and latency
measurements only. They do not contain vectors, credentials, connection URLs,
database rows, or raw driver exceptions. If no credible schema context exists,
retrieval returns a safe failure and does not authorize later SQL generation.
