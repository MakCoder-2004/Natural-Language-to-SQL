# Safe Schema-aware SQL Analytics

This project is a production-oriented natural-language-to-SQL analytics MVP for
an existing PostgreSQL database. It retrieves only relevant schema metadata,
proposes SQL through a bounded LangChain/LCEL workflow, validates it with
deterministic application code, and executes only approved read-only queries.

The MVP demonstrates schema-aware retrieval, structured model outputs, controlled
tool use, SQL safety validation, human approval, source-only execution, grounded
answers, result visualization, testing, evaluation, and structured observability.
It is intentionally not an unrestricted database agent.

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

Open `http://localhost:5173/settings` to configure a single runtime source
database from the browser. The settings page tests the PostgreSQL URL and
read-only role before saving it in backend memory, and can start the schema
index refresh. This is single-user local configuration; the connection is
cleared when the backend restarts and is never stored in browser storage.

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

## Hybrid Schema Retrieval

Milestone 4 retrieves compact schema context from the local index by combining
LangChain query embeddings, PostgreSQL keyword and identifier matching, and
weighted reciprocal-rank fusion. High-confidence tables receive bounded
foreign-key expansion, while selected columns and join keys are retained in a
structured result. Retrieval fails closed for missing, stale, failed, or
unavailable indexes and never falls back to the full schema.

Retrieval limits are backend-only settings. They cannot be supplied by a model
or browser client. The retrieval service is an internal backend capability; a
public natural-language query endpoint is introduced in a later milestone.

## Query Workflow

The public FastAPI workflow accepts a natural-language question and keeps its
state backend-side. Clear questions proceed through schema retrieval, structured
SQL generation, deterministic validation, approval when required, source-only
execution, result normalization, grounded answer generation, and visualization
selection. Ambiguous questions stop for clarification rather than guessing.

Review Mode is the default. It exposes the proposed SQL, interpretation, tables,
assumptions, validation state, and warnings before execution. Auto Mode may run
without an interactive approval step, but it still passes the same backend
validation, read-only, timeout, row, and result-size checks.

SQL edited in the browser is untrusted input. The backend revalidates the exact
edited SQL immediately before execution.

See [Backend API](docs/api/backend-api.md), [Review and Approval](docs/workflows/review-and-approval.md),
and [Basic SQL Pipeline](docs/pipeline/basic-sql-pipeline.md) for the contracts.

## Model Configuration

All model choices are backend-only environment configuration. Set
`MODEL_PROVIDER=ollama` and `OLLAMA_BASE_URL=http://host.docker.internal:11434` to
use a local Ollama chat model. The supplied local configuration uses
`qwen3.5:4b` for question analysis, SQL generation, SQL correction, and answer
generation. Ollama must be running on the host before starting the backend.

Schema indexing and retrieval still use the configured OpenRouter embedding model
(`nvidia/nemotron-3-embed-1b:free` by default). Changing the embedding model
requires rebuilding the schema index; changing a chat model does not require
workflow-code changes. Multiple logical chat roles may share one model.

See [Model Replacement](docs/models/model-replacement.md) for configuration,
timeouts, failure behavior, and the required index rebuild procedure after changing
the embedding model.

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

## Documentation

- [Local development and Compose](docs/LOCAL_DEVELOPMENT.md)
- [Architecture](docs/architecture/README.md)
- [Security](docs/security/README.md)
- [Schema retrieval](docs/retrieval/README.md)
- [Backend API](docs/api/backend-api.md)
- [Review and approval workflow](docs/workflows/review-and-approval.md)
- [Evaluation](docs/evaluation/README.md)
- [Demo walkthrough](docs/demo/README.md)
- [Model replacement](docs/models/model-replacement.md)

## MVP Scope and Limitations

The source database is deployment-specific and must be provisioned externally
with a dedicated read-only role. The repository does not create, migrate, seed,
or modify a production business schema. Representative schemas and rows are
test-only fixtures in disposable integration environments.

Query workflow state is currently held in backend process memory and is lost on
restart. The MVP does not provide multi-user authorization, additional database
engines, query-plan explanations, semantic metric governance, LangSmith tracing,
or autonomous agent behavior beyond the bounded tools.

See [Deferred Enhancements](docs/TASKS.md#deferred-enhancements) for the full
out-of-scope list.
