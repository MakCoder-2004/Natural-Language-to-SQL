# Foundation and Source Database Architecture

The application has two PostgreSQL boundaries with different responsibilities.

```text
React frontend
       |
       v
FastAPI backend ----> external source PostgreSQL
       |                         |
       |                         +--> scoped technical introspection
       |                         +--> future validated read-only execution
       v
local PostgreSQL + pgvector index
```

The external source database already owns its business schema. The backend uses
it for scoped technical schema introspection and will later use the same source
boundary for validated read-only analytics execution. No production migration
or seed path exists in this repository.

The local index database is an application-owned store for technical metadata,
version-controlled semantic metadata, schema documents, and embeddings. It is
not a copy of business rows and is never a generated-query execution target.

All connection URLs and model credentials are loaded by the backend settings
layer. The frontend receives only an API origin. The initial frontend is a
presentation shell; it has no direct database access.

FastAPI owns one typed `SourceDatabase` service and one typed `IndexDatabase`
service. They use separate SQLAlchemy engines, pools, credentials, and cleanup
paths. Source introspection and the future source executor receive the source
service explicitly; an index service cannot satisfy that dependency.

The source service constructs LangChain's `SQLDatabase` adapter from the same
source SQLAlchemy engine when SQL-oriented LangChain functionality is needed.
The adapter is scoped to an approved schema and is configured not to sample
business rows. SQLAlchemy inspection and fixed PostgreSQL catalog queries remain
authoritative for complete technical metadata, comments, relationships, index
ordering, and fingerprinting.

The source introspection pipeline is:

```text
SOURCE_DATABASE_URL
    -> source connection pool
    -> approved schema scope
    -> SQLAlchemy inspector + PostgreSQL catalogs
    -> normalized technical metadata
    -> stable SHA-256 schema fingerprint
```

The health endpoint performs bounded source and index probes. Source health also
checks the configured role's read-only permissions. Database URLs, passwords,
and raw driver errors never appear in health responses or normal logs.
