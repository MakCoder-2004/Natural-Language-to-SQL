# System Overview

```mermaid
flowchart LR
    browser[React frontend]
    api[FastAPI API]
    workflow[Deterministic LCEL workflow]
    agent[Bounded agent tools]
    validator[SQL validator and policy]
    indexer[Schema index command]
    index[(Local PostgreSQL + pgvector)]
    source[(External PostgreSQL source)]

    browser -->|questions, approval, edits| api
    api --> workflow
    workflow --> agent
    agent -->|get relevant schema| index
    workflow --> validator
    validator -->|approved read-only SQL| source
    source -->|schema metadata| indexer
    indexer -->|documents and embeddings| index
    source -->|rows| workflow
    workflow -->|results and grounded answer| api
    api --> browser
```

The external source database is used for both schema introspection and read-only
business-query execution. The local index stores technical schema metadata,
semantic metadata, documents, and embeddings only. Generated business SQL never
targets the local index.

The model proposes structured outputs inside the bounded workflow. FastAPI,
deterministic validation, approval gates, resource limits, and the source
database's read-only role remain the authorization boundary.
