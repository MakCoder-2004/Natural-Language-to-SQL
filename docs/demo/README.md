# Demo Walkthrough

This walkthrough demonstrates the complete safe query path against an
administrator-provisioned external PostgreSQL source. The source database is
not part of this repository or the Compose stack.

## Prerequisites

- Docker Desktop with Compose.
- A PostgreSQL source database with a dedicated read-only role.
- An OpenRouter API key supplied only through the backend `.env` file.
- A source schema scope containing the schema used for the demo.

Use a sanitized non-production source for portfolio demonstrations. Do not add
business data, credentials, or a fixed business schema to this repository.

## Start

1. Copy `.env.example` to `.env`.
2. Set `SOURCE_DATABASE_URL` to the external source database.
3. Set `INDEX_DATABASE_URL` to the Compose hostname:
   `postgresql+psycopg://<user>:<password>@index-db:5432/<index-database>`.
4. Set the backend-only `OPENROUTER_API_KEY` and the approved
   `SOURCE_SCHEMA_SCOPE`.
5. Start the services:

```powershell
docker compose up --build
```

6. In another terminal, build the local schema index:

```powershell
docker compose run --rm backend index-schema
```

7. Open `http://localhost:5173/` and confirm the backend health response at
   `http://localhost:8000/api/health`.

## Runtime Settings Journey

1. Open `http://localhost:5173/settings`.
2. Paste a PostgreSQL URL for the administrator-provisioned read-only role.
3. Enter the approved schema scope.
4. Select `Test connection` and confirm read-only verification succeeds.
5. Select `Save connection`, then `Index or refresh schema`.
6. Return to the workspace and submit a question matching the connected schema.
7. Confirm that disconnecting prevents new queries and does not delete the
   local index volume.

## Review Mode Journey

Use a clear question that matches the sanitized source schema, for example:

```text
Which records were created most recently, and when?
```

The exact wording must be adapted to the schema documented by the source owner.

1. Submit the question in the frontend.
2. Confirm that the application displays the proposed SQL and interpretation.
3. Review the listed tables, assumptions, validation state, and warnings.
4. Approve the validated proposal.
5. Confirm that results and the grounded answer are displayed.
6. Confirm that a suitable tabular or chart presentation is selected.

The model does not choose the database connection or authorize execution. The
backend validator and the source read-only role enforce that boundary.

## Edited SQL Journey

1. Edit the proposed SQL in the SQL Inspector.
2. Submit the edited SQL for validation.
3. Confirm that approval is cleared and the edited SQL receives a new version.
4. Approve the new validated version.
5. Confirm that the executed SQL hash matches the approved edited SQL hash.
6. Replace the SQL with an unsafe statement or an unknown table.
7. Confirm that validation rejects it and that no execution occurs.

This demonstrates that the frontend cannot reuse the original validation result.

## Clarification and Auto Mode

Submit an ambiguous question, such as a request containing an undefined metric
or date range. The workflow must request clarification, generate no SQL, and
execute no database query.

Then select Auto Mode for a clear question. Confirm that it can execute only
after the same backend validation and resource-limit checks used by Review Mode.

## Safety Boundary

The source database is used for both introspection and read-only query execution.
The local `index-db` stores schema metadata and embeddings only. Generated
business SQL must never target `index-db`.
