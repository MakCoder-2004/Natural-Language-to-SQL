# Retrieval Documentation

Document schema introspection, semantic metadata, indexing, hybrid retrieval,
and bounded relationship expansion here.

## Milestone 3 Indexing

The indexing pipeline is:

```text
external source metadata
    + version-controlled semantic metadata
    -> deterministic schema documents
    -> LangChain OpenAI-compatible embeddings configured for OpenRouter
    -> local PostgreSQL + pgvector
```

The configured embedding model is `nvidia/nemotron-3-embed-1b:free` by
default in `.env.example`. The embedding service uses LangChain's verified
`OpenAIEmbeddings` integration with OpenRouter's `/api/v1` base URL. The
indexing service does not implement a guessed provider-specific embedding
class.

Documents describe source schemas, relations, columns, foreign-key
relationships, and semantic concepts. Source business rows are never embedded.
The local index stores source fingerprints, semantic metadata digests, document
versions, model identifiers, vectors, and index-run status.

Run an initial index or refresh after source or semantic metadata changes with:

```powershell
cd backend
uv run index-schema
```

`GET /api/health` reports whether the active index is `not_initialized`,
`ready`, `stale`, `failed`, or `unavailable`.

## Milestone 4 Hybrid Retrieval

The internal `HybridSchemaRetrievalService` accepts one natural-language
question and returns a `RetrievalResult` containing:

```text
documents
tables
columns
relationships
context_text
index_fingerprint
diagnostics
```

It first requires a promoted index matching the current source fingerprint and
semantic metadata digest. It then executes two bounded LangChain retrievers:

1. `VectorSchemaRetriever` embeds the question with the same configured
   `OpenAIEmbeddings` model used at index time and queries pgvector through the
   custom local-index repository.
2. `KeywordSchemaRetriever` uses PostgreSQL `to_tsvector`,
   `plainto_tsquery`, `ts_rank_cd`, and exact structured identifier matching.

The service merges the two result lists by stable `document_key` and uses
LangChain's `EnsembleRetriever` weighted reciprocal-rank implementation. It
retains per-signal rank, raw scores, exact identifier evidence, and fused
scores for deterministic application-level table and column selection.

Table evidence is weighted by document category. Direct table documents,
semantic concepts, columns, and relationships contribute explicit category
weights. Only credible selected tables are eligible for immediate outgoing or
incoming foreign-key expansion. Expanded tables are lower priority and receive
only the relationship and join columns needed to explain the edge unless they
were independently retrieved.

The final context contains quoted source identifiers, selected PostgreSQL
types, nullability, key roles, required relationships, and relevant semantic
descriptions. It is limited by backend-controlled table, column, relationship,
document, and character bounds. It never contains source business rows,
credentials, or the full active index.

Failures are explicit and fail closed:

```text
index_not_initialized
index_stale
index_failed
index_unavailable
index_corrupt
no_relevant_schema
```

Retrieval diagnostics measure readiness, embedding/vector search, keyword
search, fusion, ranking, relationship expansion, context construction, and
total latency. The MVP records these through structured application logging;
LangSmith integration is not required.
