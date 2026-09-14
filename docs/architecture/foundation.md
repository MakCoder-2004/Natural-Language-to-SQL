# Foundation Architecture

The application has two PostgreSQL boundaries with different responsibilities.

```text
React frontend
       |
       v
FastAPI backend ----> external source PostgreSQL
       |
       v
local PostgreSQL + pgvector index
```

The external source database already owns its business schema. The backend will
later use it for technical schema introspection and read-only analytics
execution. No production migration or seed path exists in this repository.

The local index database is an application-owned store for technical metadata,
version-controlled semantic metadata, schema documents, and embeddings. It is
not a copy of business rows and is never a generated-query execution target.

All connection URLs and model credentials are loaded by the backend settings
layer. The frontend receives only an API origin. The initial frontend is a
presentation shell; it has no direct database access.

The initial FastAPI application exposes only `/api/health`. Startup records a
safe configuration summary and the health service reports whether configuration
is present. It does not introspect a database, initialize the index, call an
LLM, or execute SQL.
