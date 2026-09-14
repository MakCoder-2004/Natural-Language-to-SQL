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
- Query limits and source scope

The frontend receives no backend environment file. `VITE_API_BASE_URL` is a
public browser configuration value and does not contain credentials.

`SOURCE_SCHEMA_SCOPE` is a comma-separated list of approved PostgreSQL schema
names. It identifies schemas, not business tables. PostgreSQL system schemas
are rejected by backend configuration validation.

## Compose Lifecycle

Start the stack:

```powershell
docker compose up --build
```

The `index-db` container has a `pg_isready` health check and stores data in the
named `index_db_data` volume. The backend does not claim that the schema index
is ready until a later indexing milestone initializes it.

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
```

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

`GET /api/health` reports process availability, configuration state, whether
source and index connection settings are present, OpenRouter configuration, and
schema-index readiness.

The foundation reports configured database URLs as `configured`, not as
reachable. Database connectivity probes belong to the source/index database
milestones. Schema-index status remains `not_initialized` until indexing is
implemented.

Health responses and startup logs never include passwords, API keys, connection
URLs, stack traces, or business rows.
