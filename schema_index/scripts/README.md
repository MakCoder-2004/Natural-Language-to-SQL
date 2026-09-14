# Index Scripts

The backend project script performs schema introspection and local index refresh:

```powershell
cd backend
uv run index-schema
```

The command reads the configured external source database, creates documents
and embeddings, and writes only to the local pgvector index. It never modifies
the external source business schema. The command is repeatable and replaces
stale active documents atomically.

The Compose equivalent is:

```powershell
docker compose run --rm backend index-schema
```
