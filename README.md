# Safe Schema-aware SQL Analytics

This project is a production-oriented natural-language-to-SQL analytics
application for an existing PostgreSQL database. It retrieves relevant schema
metadata, proposes SQL, validates it deterministically, and executes only
approved read-only queries.

The project is currently at Milestone 1: Project Foundation. The repository
contains the runtime skeleton, configuration boundaries, local index service,
and initial health reporting. Query generation and schema indexing are added in
later milestones.

## Architecture Boundary

The source PostgreSQL database is external to the Compose stack. It remains the
source of technical schema metadata and the target for future read-only query
execution. The application must not create, migrate, seed, or modify its
business schema.

The local `index-db` service is a separate PostgreSQL database with pgvector.
It will store schema metadata, documents, and embeddings. It must never become
the target for generated business SQL. Its data is stored in the persistent
`index_db_data` Docker volume.

The React frontend communicates only with FastAPI. Database URLs, database
credentials, and the OpenRouter key are backend-only configuration.

## Local Startup

Prerequisites are Docker Desktop with Compose, Node.js compatible with the
frontend manifest, and `uv` with Python 3.12 for direct backend development.

1. Copy `.env.example` to `.env`.
2. Replace every angle-bracket placeholder with local or deployment-specific
   configuration.
3. Set `INDEX_DATABASE_URL` to the Compose service address, for example
   `postgresql+psycopg://index_user:<password>@index-db:5432/schema_index`.
4. Set `SOURCE_DATABASE_URL` to the external read-only source database.
5. Start the services with the Compose command defined by `compose.yaml`:

```powershell
docker compose up --build
```

The frontend is available at `http://localhost:5173` and the backend health
endpoint is available at `http://localhost:8000/api/health`.

The source database is not started by Compose. Its network access depends on
the configured environment. A missing source URL leaves the backend available
for health diagnostics but reports a degraded configuration state.

Stop the services without removing the local index volume:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless the local schema-index data should be
deleted.

## Direct Development Commands

The backend commands are provided by `backend/pyproject.toml` and its `uv.lock`:

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app tests
uv run pytest
```

The frontend commands are defined in `frontend/package.json`:

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

## Scope

Milestone 1 intentionally does not include a fixed business schema, source
migrations, source seed data, SQL generation, SQL validation, schema indexing,
or database query execution. Representative test schemas and rows belong only
under `tests/fixtures/` when later tests need them.
