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
