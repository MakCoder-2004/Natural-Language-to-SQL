# Local Development

## Services

`compose.yaml` starts three services:

| Service | Responsibility | Data boundary |
|---|---|---|
| `frontend` | React development application | Receives only the public FastAPI URL. |
| `backend` | FastAPI application and future orchestration | Owns all database URLs, model configuration, and secrets. |
| `index-db` | Local PostgreSQL + pgvector service | Stores schema-index metadata, documents, and embeddings only. |

The source PostgreSQL database is intentionally external to Compose. It is not
replaced by a local seeded business database. Future source introspection and
read-only execution will use the same configured source database.

## Configuration

Copy `.env.example` to `.env` and replace all placeholders. The local Compose
index connection must use the service hostname `index-db`; a host-side client
may use a separately configured port if one is added later.

The following values are backend-only:

- `SOURCE_DATABASE_URL`
- `INDEX_DATABASE_URL`
- `OPENROUTER_API_KEY`
- Model role identifiers
- Semantic metadata path and OpenRouter attribution values
- Query, retrieval, and context limits
- Source scope

The frontend receives no backend environment file. `VITE_API_BASE_URL` is a
public browser configuration value and does not contain credentials.

`SOURCE_SCHEMA_SCOPE` is a comma-separated list of approved PostgreSQL schema
names. It identifies schemas, not business tables. PostgreSQL system schemas
are rejected by backend configuration validation. The source introspector fails
closed when a configured schema does not exist.

Database connection settings are backend-only. Pool settings control the bounded
SQLAlchemy engines, `DATABASE_CONNECT_TIMEOUT_SECONDS` controls connection
attempts, and `QUERY_TIMEOUT_SECONDS` becomes PostgreSQL's server-side
`statement_timeout`.

## External Source Role

The source database must already exist and must be administered outside this
repository. Use a dedicated read-only role with `CONNECT`, schema `USAGE`, and
`SELECT` on the approved scope. Do not make that role an object owner or grant
it `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`,
superuser, replication, or role/database administration privileges.

The backend verifies these permissions using PostgreSQL catalog functions. It
does not create roles, alter permissions, or probe write/DDL operations against
the real source database.

## Compose Lifecycle

Start the stack:

```powershell
docker compose up --build
```

The `index-db` container has a `pg_isready` health check and stores data in the
named `index_db_data` volume. The backend does not claim that the schema index
is ready until the indexing command completes successfully. Initialize or
refresh it with:

```powershell
docker compose run --rm backend index-schema
```

Inspect service state:

```powershell
docker compose ps
```

Check the backend:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

Stop the stack while preserving the volume:

```powershell
docker compose down
```

Use `docker compose down -v` only when intentionally deleting local index
storage.

## Direct Development

Backend setup and checks use `uv` from `backend/pyproject.toml`:

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app tests
uv run pytest
uv run pytest tests/integration -m integration
```

After a successful index run, the internal
`HybridSchemaRetrievalService` combines vector and PostgreSQL keyword signals
from `index-db`. Retrieval requires a ready index whose source fingerprint and
semantic metadata digest match the current source. It does not expose a public
query route yet and it never queries business rows for schema retrieval.

Frontend setup and checks use npm scripts from `frontend/package.json`:

```powershell
cd frontend
npm install
npm run dev
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

## Health Semantics

`GET /api/health` reports process availability, configuration state, source and
index connectivity, source read-only verification, OpenRouter configuration,
and schema-index readiness and freshness.

Database components can report `not_configured`, `invalid`, `not_checked`,
`reachable`, `unavailable`, or `permission_denied`. The schema-index status can
report `not_initialized`, `ready`, `stale`, `failed`, or `unavailable`.

`ready` means the latest successful index fingerprint and semantic metadata
digest match the current source and configured metadata. `stale` means an
active index exists but must be refreshed before relying on it for retrieval.

Health responses and startup logs never include passwords, API keys, connection
URLs, stack traces, or business rows.

## Schema Indexing

Version-controlled semantic metadata lives under `schema_index/metadata`. The
index command performs source introspection, deterministic document generation,
LangChain embedding generation through OpenRouter, and atomic local index
promotion. It never writes to the external source database.

For direct development:

```powershell
cd backend
uv run index-schema
```
