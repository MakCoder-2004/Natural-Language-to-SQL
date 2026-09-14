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
read-only role. Those controls are not implemented in this foundation phase,
but the configuration and directory boundaries reserve the correct ownership.

## Untrusted Inputs

Frontend values and future model output are not authorization decisions. The
health endpoint does not accept connection details from either client input or
model output. Later milestones must preserve backend validation, approval, and
exact-SQL checks at every execution boundary.
