# Safe Schema-aware SQL Analytics

This project is a production-oriented natural-language-to-SQL analytics
application for an existing PostgreSQL database. It retrieves relevant schema
metadata, proposes SQL, validates it deterministically, and executes only
approved read-only queries.

The project is currently at Milestone 3: Schema Documentation and Indexing. The
repository contains isolated source and index database services, scoped
PostgreSQL metadata introspection, read-only access verification, versioned
semantic metadata, deterministic schema documents, LangChain-backed OpenRouter
embeddings, repeatable pgvector indexing, and index freshness reporting.
Query retrieval and SQL generation are added in later milestones.

## Architecture Boundary

The source PostgreSQL database is external to the Compose stack. It remains the
source of technical schema metadata and the target for future read-only query
execution. The application must not create, migrate, seed, or modify its
business schema. The backend introspects only the schemas listed in
`SOURCE_SCHEMA_SCOPE` and rejects PostgreSQL system schemas.

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
5. Provision the source role described in [Source Role](#source-role).
6. Start the services with the Compose command defined by `compose.yaml`:

```powershell
docker compose up --build
```

The frontend is available at `http://localhost:5173` and the backend health
endpoint is available at `http://localhost:8000/api/health`.

Run the initial schema index from another terminal:

```powershell
docker compose run --rm backend index-schema
```

The backend reads technical metadata from the external source, merges the
version-controlled files under `schema_index/metadata`, generates embeddings,
and writes documents only to the local `index-db` service.

The source database is not started by Compose. Its network access depends on
the configured environment. A missing source URL leaves the backend available
for health diagnostics but reports a degraded configuration state. A configured
source URL is not enough for readiness: the health endpoint also checks
connectivity and read-only access.

## Source Role

The source URL must use a PostgreSQL role owned and provisioned by the database
administrator. The role should have `CONNECT`, schema `USAGE`, and `SELECT` on
the approved source scope only. It must not own source objects or have write,
DDL, elevated-role, replication, or row-level-security-bypass privileges.

The application verifies these properties from PostgreSQL privilege metadata. It
does not create the role and does not issue write or DDL probes against the
external source database. A representative administrator-managed setup is:

```sql
CREATE ROLE nl2sql_reader LOGIN PASSWORD '<strong-password>';
GRANT CONNECT ON DATABASE <source-database> TO nl2sql_reader;
GRANT USAGE ON SCHEMA <approved-schema> TO nl2sql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA <approved-schema> TO nl2sql_reader;
REVOKE CREATE ON DATABASE <source-database> FROM nl2sql_reader;
REVOKE CREATE ON SCHEMA <approved-schema> FROM nl2sql_reader;
```

Grant statements must be adapted to the deployment's ownership and default
privilege policy. The application never runs these statements.

Stop the services without removing the local index volume:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless the local schema-index data should be
deleted.

## Schema Metadata and Index Refresh

Semantic metadata is versioned under `schema_index/metadata`. It uses
`metadata_version: 1` and structured source identifiers for schemas, relations,
columns, relationships, and semantic concepts. Technical PostgreSQL metadata
remains authoritative, and stale semantic references are reported without
creating fictional source objects.

The default embedding model is:

```text
nvidia/nemotron-3-embed-1b:free
```

It is called through LangChain's `OpenAIEmbeddings` integration configured with
OpenRouter's OpenAI-compatible embeddings endpoint. The model ID remains
configuration-driven.

Refresh after source schema or semantic metadata changes:

```powershell
docker compose run --rm backend index-schema
```

The operation is idempotent. It stages a complete run and promotes it
atomically, preserving the previous active index when embedding or database
work fails. It never writes to the external source schema.

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
uv run pytest tests/integration -m integration
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

Milestone 3 still does not include hybrid retrieval, SQL generation, SQL
validation, or public database query execution. Representative test schemas
and rows belong only under `backend/tests/fixtures/` and are created inside
disposable integration containers.
