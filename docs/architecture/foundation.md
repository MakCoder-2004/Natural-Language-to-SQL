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

## Schema Indexing

Milestone 3 extends the pipeline without changing the source boundary:

```text
technical source snapshot + versioned semantic metadata
    -> deterministic table, column, relationship, and concept documents
    -> LangChain OpenAI-compatible embeddings configured for OpenRouter
    -> staged local pgvector rows
    -> atomic active-index promotion
```

The configured default embedding model is
`nvidia/nemotron-3-embed-1b:free`. The implementation uses LangChain's verified
`OpenAIEmbeddings` class with `OPENROUTER_BASE_URL` set to OpenRouter's
OpenAI-compatible API base. The application owns the provider-neutral embedding
contract and validation, but does not implement a guessed provider-specific
LangChain class.

The local index uses a dedicated `nl2sql_index` PostgreSQL schema containing
index runs, normalized metadata, rendered documents, and pgvector embeddings.
Index initialization executes only against `IndexDatabase`. A complete run is
staged first and promoted transactionally, so a failed refresh cannot destroy
the previous active index.

The index stores technical metadata and application-controlled semantic
descriptions only. Source business rows are never sampled or embedded. The
health endpoint compares the active source fingerprint and semantic metadata
digest with the current source and configuration before reporting `ready`.

## Hybrid Retrieval

Milestone 4 keeps the local index repository as the storage boundary and uses
LangChain for the retrieval integration boundary:

```text
natural-language question
        |
        +--> LangChain OpenAI-compatible query embedding
        |          -> bounded pgvector search in index-db
        |
        +--> PostgreSQL full-text and identifier search in index-db
                   |
                   v
        LangChain weighted reciprocal-rank fusion
                   |
                   v
        deterministic table/column ranking
                   |
                   v
        bounded foreign-key expansion
                   |
                   v
        compact structured schema context
```

The retrieval service validates index readiness before either search signal
runs. It derives the source key and current fingerprint from backend-owned
source metadata, but all candidate documents, vectors, and relationship reads
come from `IndexDatabase`. It does not use LangChain's deprecated community
`PGVector` storage because that would create a second unmanaged index schema.

Vector and keyword results are exposed through LangChain `BaseRetriever`
adapters and `Document` values. LangChain's `EnsembleRetriever` weighted
reciprocal-rank function provides the initial signal fusion; application code
then applies table selection, relationship bounds, source validation, and
context-size limits. The model cannot control source scope, database handles,
retrieval limits, or index SQL.

The health endpoint performs bounded source and index probes. Source health also
checks the configured role's read-only permissions. Database URLs, passwords,
and raw driver errors never appear in health responses or normal logs.
