# Safe Schema-Aware Natural-Language-to-SQL Analytics Platform

## Project Implementation Specification

This document is the implementation plan and requirement specification for the MVP. It is intentionally more detailed than a milestone list. It defines the product behavior, architecture, data flow, security boundaries, interfaces, operational constraints, tests, and acceptance criteria.

The source requirements are `docs/PRD.md`, the flow diagrams in `Flow Diagram/`, and the decisions confirmed during review. When this document differs from the original PRD because of a confirmed decision, this document is authoritative for implementation.

---

## 1. Project Identity

### 1.1 Product name

Safe Schema-Aware Natural-Language-to-SQL Analytics Platform.

### 1.2 Product description

This is a production-oriented analytics application that lets a technical or semi-technical user ask questions about an existing PostgreSQL database in plain English. The application retrieves only the relevant database schema, proposes SQL through LangChain and an OpenRouter model, validates the proposal with deterministic application code, optionally obtains user approval, executes only safe read-only SQL, and returns transparent, grounded results.

This is not simply an AI chatbot that writes SQL. The project demonstrates how an LLM can be used in a database application without making the LLM the security boundary.

### 1.3 Portfolio positioning

The project should demonstrate:

- Natural-language database querying.
- Schema RAG and hybrid retrieval.
- Relationship-aware schema context building.
- LangChain and LCEL integration.
- Structured model outputs.
- Controlled tool use.
- Deterministic SQL validation.
- Human approval and SQL transparency.
- Read-only PostgreSQL execution.
- Grounded answer generation.
- Result visualization.
- Testing, evaluation, and observability.

### 1.4 Primary technology stack

- Python.
- LangChain.
- LCEL.
- FastAPI.
- React.
- PostgreSQL.
- pgvector.
- SQLAlchemy and a PostgreSQL driver through the selected LangChain integration.
- OpenRouter.
- Docker Compose for the application and local schema-index services.

Model and package APIs must be checked against the versions selected during implementation. The implementation must use current LangChain abstractions rather than copying or recreating them.

---

## 2. Confirmed Architectural Decisions

These decisions resolve the conflicts between the PRD and the diagrams.

### 2.1 Existing source database

There is no predefined application business schema for the MVP. The application connects to a real, existing PostgreSQL database through a backend-only connection URL.

The same source database is used for both:

- Schema introspection.
- Read-only query execution.

The tables shown in the PRD, such as `customers`, `orders`, and `products`, are examples of a possible domain, not hardcoded MVP requirements.

The application must not create, migrate, seed, or modify the source database business schema.

### 2.2 Separate schema index database

Schema documents and embeddings are stored in a separate local PostgreSQL database with pgvector.

The source database and the index database have different purposes:

```text
Source PostgreSQL database
  - Existing business data
  - Source of technical schema metadata
  - Read-only query target

Local index PostgreSQL database
  - Schema documents
  - Technical and semantic metadata
  - Embeddings and vector search
  - No business rows
```

The local index database must never be used as the target for generated business queries.

### 2.3 Controlled agent

The MVP uses the diagram's controlled tool-using agent, but not an unrestricted autonomous database agent.

The agent can use only these application-owned tools:

- `get_relevant_schema`.
- `generate_sql`.
- `execute_readonly_sql`.

The deterministic application workflow owns state transitions, approval gates, validation, retry limits, resource limits, and database connections. The agent cannot create tools, choose a database connection, execute arbitrary SQL, or bypass application policy.

The controlled agent is therefore a bounded tool caller inside the deterministic LCEL workflow.

### 2.4 Deterministic SQL validation

The diagram's `Schema Validation` node means the PRD's deterministic SQL validation stage. It must validate both:

- SQL safety and statement policy.
- References against the approved, dynamically introspected source schema.

Validation is independent of model instructions and frontend state.

### 2.5 Edited SQL

Edited SQL is untrusted input. Every SQL string supplied by the frontend must be fully revalidated by the backend immediately before execution.

The frontend must never be allowed to execute based only on the original validation result.

### 2.6 MVP observability

The MVP uses structured FastAPI/application logging only.

The following are deferred:

- A separate proxy service for logging.
- LangSmith integration.

The backend still records query IDs, stage telemetry, validation results, retry counts, and final status.

---

## 3. Goals

### 3.1 Natural-language querying

Users can ask questions about the connected PostgreSQL database without writing SQL manually.

The application must support questions involving, where the connected source schema supports them:

- Lookups.
- Filtering.
- Aggregation.
- Sorting.
- Joins.
- Date and time analysis.
- Multi-table analysis.
- Nested queries.

The application must not assume that any particular business table exists.

### 3.2 Ambiguity handling

The system must not silently choose an interpretation when a question is materially ambiguous.

The analysis stage must identify ambiguity in concepts such as:

- Metric meaning.
- Entity meaning.
- Date range.
- Status definitions.
- Ranking terms such as "best" or "most active".
- Scope of the requested data.

When clarification is required:

- No SQL is generated.
- No database query is executed.
- The user receives a concise clarification request.
- The query remains associated with its query ID.

### 3.3 Schema-aware retrieval

The entire source schema must not be sent to the model for every request when relevant context can be selected.

The runtime pipeline must retrieve:

- Relevant tables.
- Relevant columns.
- Required relationships.
- Business definitions from semantic metadata.
- PostgreSQL dialect information.
- Safety guidance.

### 3.4 Safe read-only execution

Only validated read-only SQL may reach the execution layer.

The source PostgreSQL role used for runtime execution must also be read-only. Application policy and database permissions provide defense in depth.

### 3.5 Transparency

Review Mode must expose enough information for the user to understand what will be executed:

- SQL text.
- Interpretation.
- Tables used.
- Assumptions.
- Validation state.
- Warnings.
- Result and explanation after execution.

### 3.6 Replaceable models

OpenRouter model identifiers must be configuration-driven. Model IDs must not be scattered through source code.

The MVP may use one model for multiple roles, but role boundaries must remain explicit.

### 3.7 Quality and portfolio value

Each major stage must be inspectable, testable, replaceable, and measurable.

---

## 4. Non-Goals

The MVP does not:

- Create a fixed business schema.
- Create or modify tables in the source database.
- Seed production or user-provided source data.
- Execute `INSERT`.
- Execute `UPDATE`.
- Execute `DELETE`.
- Execute `DROP`.
- Execute `ALTER`.
- Execute `TRUNCATE`.
- Execute `CREATE`.
- Execute `GRANT`.
- Execute `REVOKE`.
- Expose database credentials to React.
- Expose database credentials to the LLM.
- Give an autonomous agent unrestricted database access.
- Support database engines other than PostgreSQL.
- Guarantee perfect semantic correctness for every question.
- Replace a full BI platform.
- Require a separate proxy service.
- Require LangSmith.

Test fixtures may create temporary schemas and data solely for automated testing. That does not change the production behavior or source-database contract.

---

## 5. Users and User Experience

### 5.1 Primary user

A technical or semi-technical user who wants insights from a PostgreSQL database without manually writing SQL.

### 5.2 Core user journey: clear question in Review Mode

1. The user opens the React application.
2. The user enters a natural-language question.
3. The frontend sends the question and execution mode to FastAPI.
4. The backend creates a query ID.
5. The backend analyzes the question.
6. The backend retrieves relevant schema context.
7. The backend generates a structured SQL proposal.
8. The deterministic validator checks the SQL.
9. If validation fails, the controlled correction loop may retry up to two times.
10. If validation passes, the backend returns the SQL Inspector state.
11. The user reviews the SQL, interpretation, tables, assumptions, validation, and warnings.
12. The user approves the query or edits the SQL.
13. If edited, the backend fully revalidates the edited SQL.
14. The backend executes the exact validated SQL against the source database.
15. The backend normalizes the returned rows.
16. The backend generates a grounded natural-language answer.
17. The frontend displays the answer, table, and a chart when appropriate.

### 5.3 Core user journey: ambiguous question

1. The user submits an ambiguous question.
2. The analysis stage returns `CLARIFICATION_REQUIRED`.
3. The frontend displays a clarification panel.
4. The user selects or writes a clarification.
5. The backend combines the original question with the clarification context.
6. The pipeline resumes analysis.
7. SQL is not generated before clarification is received.

### 5.4 Core user journey: Auto Mode

1. The user submits a question with Auto Mode selected.
2. The same analysis, retrieval, generation, and validation stages run.
3. A valid query can execute without an approval click.
4. Deterministic validation is never skipped.
5. The read-only source database role is still used.
6. Unsafe or invalid SQL is rejected or corrected according to the bounded retry policy.

### 5.5 Core user journey: SQL correction

1. SQL generation returns a proposal.
2. Validation detects a correctable problem.
3. The correction stage receives safe error context and the prior proposal.
4. A new proposal is generated.
5. The new proposal is validated again.
6. This can happen at most two correction attempts.
7. If the limit is exhausted, the query fails with a user-facing message.

### 5.6 Core user journey: SQL edit

1. The user edits SQL in the SQL Inspector.
2. The frontend submits the edited SQL to FastAPI.
3. The backend treats the edited SQL as untrusted input.
4. The backend parses and validates the exact edited SQL.
5. The backend rejects it if any policy fails.
6. Only the validated edited SQL may execute.

---

## 6. System Architecture

### 6.1 Runtime components

```text
User
  |
  v
React frontend
  |
  v
FastAPI backend
  |
  +--> Query service and deterministic workflow
  |      |
  |      +--> Question analysis
  |      +--> Controlled agent / bounded tools
  |      +--> LCEL chains
  |      +--> SQL validator and policy layer
  |      +--> Result processing
  |      +--> Answer generation
  |
  +--> Local schema-index PostgreSQL + pgvector
  |      |
  |      +--> Technical metadata
  |      +--> Semantic metadata
  |      +--> Schema documents
  |      +--> Embeddings
  |      +--> Vector and metadata retrieval
  |
  +--> Existing source PostgreSQL database
         |
         +--> Schema introspection
         +--> Read-only SQL execution
```

### 6.2 Docker Compose responsibilities

Docker Compose runs:

- `frontend`: React application.
- `backend`: FastAPI, LangChain, LCEL, validation, indexing, and query execution.
- `index-db`: local PostgreSQL with pgvector for schema metadata and embeddings.

The real source PostgreSQL database is external to this Compose stack and is reached using `SOURCE_DATABASE_URL`.

The index database must use a persistent Docker volume so recreation of the index container does not unexpectedly destroy the indexed schema.

The source database must not be replaced by a local seeded business database in the MVP.

### 6.3 Request trust boundary

```text
React input and edited SQL
        |
        v
FastAPI transport validation
        |
        v
Application state and policy checks
        |
        v
Deterministic SQL validator
        |
        v
Approval gate when Review Mode is active
        |
        v
Source PostgreSQL read-only role
```

The LLM is untrusted. Model output, user input, database values, and frontend validation state must not be treated as security decisions.

### 6.4 Knowledge, reasoning, and execution layers

Knowledge layer:

```text
Existing source PostgreSQL schema
  -> Schema introspection
  -> Technical metadata
  -> Semantic enrichment
  -> Schema documents
  -> Embeddings
  -> Local pgvector index
```

Reasoning layer:

```text
Question
  -> Ambiguity analysis
  -> Hybrid schema retrieval
  -> Relationship expansion
  -> Schema ranking and context building
  -> SQL proposal
  -> Controlled correction when needed
```

Execution layer:

```text
SQL validation
  -> SQL Inspector
  -> Review approval or validated Auto Mode
  -> Backend re-validation
  -> Source database read-only execution
  -> Result normalization
  -> Answer and visualization
```

---

## 7. Database Connections and Storage

### 7.1 Source database connection

The source database connection is configured with a server-side connection URL:

```text
SOURCE_DATABASE_URL=postgresql+psycopg://readonly_user:<secret>@host:5432/database
```

The exact driver URL format must match the selected SQLAlchemy and PostgreSQL driver versions.

The source URL is used by the backend only. It is never returned to React, placed in an LLM prompt, or included in normal logs.

The backend owns the source connection and uses the LangChain SQL database abstraction for SQL-oriented database integration where appropriate.

### 7.2 Index database connection

The local index database connection is configured separately:

```text
INDEX_DATABASE_URL=postgresql+psycopg://index_user:<secret>@index-db:5432/schema_index
```

The index connection may write schema documents and embeddings. Its credentials are also backend-only.

### 7.3 Connection separation

The application must maintain separate database handles for:

- Source introspection.
- Source read-only SQL execution.
- Local index reads and writes.

The application must not accidentally pass the index connection to `execute_readonly_sql`.

The execution tool must have an explicit source-database dependency rather than selecting a connection from model-provided input.

### 7.4 Source schema scope

The source schema is dynamic, but the application still needs a safe exposure scope.

At indexing setup, the application must determine which source schemas are eligible for retrieval and execution. The default scope must exclude PostgreSQL system schemas and internal metadata that are not intended for analytics.

The eligible schemas and tables are derived from introspection and optional configuration. They must not be a hardcoded list of business table names.

### 7.5 Source role permissions

The runtime source role should have only the permissions required to:

- Read approved business schemas and tables.
- Read the metadata required for introspection.

It must not have permission to:

- Insert.
- Update.
- Delete.
- Drop.
- Alter.
- Truncate.
- Create.
- Grant.
- Revoke.

If a separate indexing role is required by a particular PostgreSQL deployment, it must still never be used for runtime generated-query execution. The source business schema must not be modified by indexing.

### 7.6 Index database contents

The index database stores metadata, not the source business rows.

It should store enough information to support:

- Source database identity or schema fingerprint.
- Source schema name.
- Table name.
- Column names and types.
- Primary keys.
- Foreign keys.
- Relationship metadata.
- Nullable information.
- Index metadata where useful.
- Table and column descriptions.
- Semantic descriptions.
- Rendered schema documents.
- Embedding vectors.
- Document type and source identifiers.

The index must not be used to answer user data questions by copying business rows into it.

---

## 8. Schema Introspection and Documentation Pipeline

### 8.1 Pipeline purpose

Before runtime user queries, the application builds a searchable schema knowledge index from the connected source PostgreSQL database.

The pipeline is precomputed. It is not rebuilt from scratch for every user question.

### 8.2 Pipeline flow

```text
SOURCE_DATABASE_URL
        |
        v
PostgreSQL schema introspection
        |
        v
Technical metadata -------------------+
                                       |
Version-controlled semantic metadata --+--> Schema document builder
                                                   |
                                                   v
                                           Rich schema documents
                                                   |
                                                   v
                                           Embedding model
                                                   |
                                                   v
                                   Local PostgreSQL + pgvector index
```

### 8.3 Introspection metadata

The introspection layer must collect, where accessible:

- Source schema names.
- Table names.
- Column names.
- Data types.
- Primary keys.
- Foreign keys.
- Foreign-key relationships.
- Nullable and non-nullable information.
- Indexes where useful.
- Table comments.
- Column comments where available.
- Relationship cardinality where it can be derived reliably.

PostgreSQL remains the source of truth for technical metadata.

### 8.4 Semantic metadata

Technical metadata does not fully explain business meaning. The application must support a version-controlled semantic metadata layer for important tables, columns, metrics, statuses, and relationships.

Semantic metadata should be keyed to the dynamically discovered source objects rather than defining a fixed application schema.

Conceptual example:

```yaml
source_schema: public
table: orders
description: Represents customer purchases.
business_meaning:
  total_amount: Total monetary amount associated with an order.
  status: Lifecycle status of the order.
  order_date: Date the order was placed.
relationships:
  - from: orders.customer_id
    to: customers.id
```

Semantic metadata must remain separate from untrusted database row values. It is application-controlled input to document building, not instructions extracted from arbitrary data.

### 8.5 Schema document builder

The document builder combines technical metadata and semantic metadata into rich retrieval documents.

A table document should include:

- Source schema and table name.
- Human-readable description.
- Relevant columns.
- Column types.
- Primary-key information.
- Foreign-key information.
- Relationships.
- Business definitions.
- Useful analytical concepts.

A relationship document should include:

- Source column.
- Target column.
- Relationship direction.
- Relationship meaning.
- Relevant question types.

Bare table names are not sufficient retrieval documents.

### 8.6 Indexing behavior

The indexing process must:

- Run during initial setup.
- Be runnable after source schema changes.
- Be runnable after semantic metadata changes.
- Be idempotent.
- Replace or version stale documents rather than creating uncontrolled duplicates.
- Record the source schema fingerprint used to generate the index.
- Fail clearly when the source database cannot be reached.
- Avoid writing to the source database business schema.

The MVP should provide a repeatable indexing command or backend operation for initial setup and refreshes.

### 8.7 Index freshness

If the source schema changes, the index must be refreshed before relying on the new objects in retrieval or SQL generation.

The application should expose an index health state that can distinguish:

- Index is available and matches the latest known source fingerprint.
- Index is available but may be stale.
- Index is missing.
- Indexing failed.

The runtime validator must not approve references that are outside the currently approved indexed source scope.

---

## 9. Hybrid Schema Retrieval

### 9.1 Retrieval requirements

Retrieval must use more than embeddings alone.

The MVP combines:

- Semantic vector retrieval.
- Keyword or metadata retrieval.
- Bounded relationship expansion.
- Ranking and filtering.

### 9.2 Index-time embedding

During indexing:

1. Rich schema documents are created.
2. The configured embedding model embeds each document.
3. Vectors and document metadata are stored in local pgvector.

The embedding model is configured through `EMBEDDING_MODEL` and is replaceable.

### 9.3 Query-time retrieval

For each clear question:

1. The question is embedded.
2. Vector retrieval finds semantically similar schema documents.
3. Keyword/metadata retrieval finds exact identifiers and terminology.
4. Candidate documents are merged and deduplicated.
5. High-confidence candidate tables are selected.
6. Immediate relationships are expanded with a bounded depth.
7. Candidates are ranked.
8. Irrelevant documents are filtered.
9. A compact final schema context is created.

### 9.4 Relationship expansion

Independent table retrieval is not sufficient for join questions.

After initial retrieval, the application should expand immediate foreign-key relationships from high-confidence candidates. Expansion must be bounded and must not return the entire graph by default.

The expansion result must preserve relationship direction and join columns.

### 9.5 Final schema context

The SQL generation stage receives only the compact context needed for the question:

```text
Original question
+ Clarification context, if any
+ Relevant source schemas and tables
+ Relevant columns and types
+ Primary and foreign keys
+ Required relationships
+ Semantic business definitions
+ PostgreSQL dialect guidance
+ Safety requirements
```

The context must not contain database credentials or unnecessary business rows.

### 9.6 Retrieval failure behavior

If retrieval returns no credible schema context:

- Do not guess tables or columns.
- Do not generate SQL from an empty schema.
- Return a useful failure or clarification message.
- Record the retrieval failure in telemetry.

---

## 10. Controlled Agent and Tool Contracts

### 10.1 Agent constraints

The controlled agent:

- Runs inside the backend.
- Uses LangChain tool abstractions.
- Has access only to application-defined tools.
- Receives no connection strings or credentials.
- Cannot issue arbitrary database introspection.
- Cannot issue arbitrary SQL execution.
- Cannot bypass the validator.
- Cannot bypass Review Mode approval.
- Cannot change the retry limit.
- Cannot alter the selected source database.

The application, not the model, determines when execution is permitted.

### 10.2 `get_relevant_schema`

Purpose: retrieve compact schema context from the local index database.

Conceptual input:

```json
{
  "question": "natural language question",
  "source_scope": "configured source scope",
  "top_k": "application-controlled limit"
}
```

The model must not control unrestricted `top_k`, source connections, or index SQL.

Conceptual output:

```json
{
  "documents": [],
  "tables": [],
  "columns": [],
  "relationships": [],
  "context_text": "compact schema context",
  "index_fingerprint": "source schema fingerprint"
}
```

The tool returns metadata and schema documentation, not source business rows.

### 10.3 `generate_sql`

Purpose: generate a structured SQL proposal from the question and retrieved schema context.

Conceptual input:

```json
{
  "question": "original question",
  "clarification_context": "optional clarification",
  "schema_context": "retrieved compact context",
  "previous_sql": "optional prior proposal",
  "validation_error": "optional safe correction context"
}
```

Conceptual output:

```json
{
  "sql": "SELECT ...",
  "interpretation": "what the query calculates",
  "tables_used": ["schema.table"],
  "assumptions": ["explicit assumptions"],
  "warnings": ["potential concerns"]
}
```

The output must be parsed as structured data. Free-form output must not be sent directly to execution.

### 10.4 `execute_readonly_sql`

Purpose: execute an exact, already-authorized SQL statement against the source database.

The tool must receive execution authorization from application state, not from the model. It must verify:

- Query ID is valid.
- Query state permits execution.
- The SQL string is the exact string that was validated.
- The backend validator passed.
- The source scope has not changed in a way that invalidates the approval.
- Resource limits are attached.

Conceptual input:

```json
{
  "query_id": "backend query ID",
  "validated_sql": "exact validated SQL",
  "sql_hash": "hash of exact SQL",
  "execution_mode": "REVIEW or AUTO"
}
```

The model must not provide a connection URL, database name, username, or password.

---

## 11. Deterministic LCEL Query Workflow

### 11.1 Workflow ownership

The deterministic application workflow owns:

- Request validation.
- Query ID creation.
- State transitions.
- Model role selection.
- Tool availability.
- Retrieval limits.
- SQL validation.
- Correction count.
- Approval policy.
- Execution authorization.
- Query and result limits.
- Error mapping.
- Observability.

The controlled agent may assist with bounded tool calls, but it does not own these policies.

### 11.2 Full flow

```text
Receive question
  -> Analyze intent
  -> If ambiguous, request clarification
  -> Retrieve schema
  -> Expand relationships
  -> Rank and build compact context
  -> Generate structured SQL
  -> Deterministically validate SQL
  -> If invalid, correct up to 2 times
  -> If valid, prepare SQL Inspector
  -> Review approval or validated Auto Mode
  -> Revalidate exact execution SQL
  -> Execute against source PostgreSQL read-only role
  -> Normalize result
  -> Generate grounded answer
  -> Select visualization from result shape
  -> Return final response
```

### 11.3 Question analysis output

The analysis stage should identify:

- Requested metric.
- Entities.
- Filters.
- Time range.
- Grouping.
- Ordering.
- Limit or top-N request.
- Likely source tables.
- Potentially ambiguous terms.
- Whether the question appears answerable from the retrieved source scope.

The analysis result should be structured and validated before later stages use it.

### 11.4 Clarification policy

Material ambiguity ends the current pipeline attempt before SQL generation.

Clarification responses should:

- Explain what is ambiguous.
- Offer concise alternatives where possible.
- Preserve the original question.
- Preserve the query ID.
- Avoid making a default business interpretation silently.

### 11.5 SQL generation policy

The SQL model receives:

- Original question.
- Clarification context.
- Relevant schema context.
- Relationships.
- Business definitions.
- PostgreSQL dialect guidance.
- Safety requirements.

It must return SQL, interpretation, tables used, and assumptions as structured output.

### 11.6 Correction policy

Correction is allowed only for correctable generation, validation, or execution errors.

The correction loop must:

- Pass only the necessary safe error context to the model.
- Preserve the original user intent.
- Rebuild or verify schema context where needed.
- Generate a new structured proposal.
- Re-run deterministic validation.
- Stop after two correction attempts.

There must be no indefinite retry loop.

### 11.7 Result processing

The backend normalizes database results into a stable representation:

```json
{
  "columns": ["column_a", "column_b"],
  "rows": [
    ["value_a", 123]
  ],
  "row_count": 1,
  "truncated": false
}
```

The normalized result is used by:

- Results table.
- Chart selection.
- Answer generation.

The answer model receives:

- Original question.
- SQL that actually executed.
- Normalized returned result.
- Relevant context where needed.

The answer stage must summarize only what is supported by the result and must not invent values or conclusions.

### 11.8 Visualization selection

Charts are selected from the returned data shape, not from a blanket instruction to always chart.

Suggested mappings:

- Metric over time: line chart.
- Category and metric: bar chart.
- Small composition: pie/donut or bar chart.
- Raw records: table.
- Single metric: KPI card.

The backend or frontend may determine chart suitability, but the decision must use normalized result structure and must safely handle unsupported shapes.

---

## 12. SQL Validation and Security Policy

### 12.1 Validator role

The SQL validator is a deterministic application security component. It must not depend on the model correctly following a prompt.

The validator must produce:

- Pass or fail result.
- Human-readable messages.
- Machine-readable failure categories.
- Warnings separate from blocking errors.
- Tables and schemas detected in the statement.
- Applied limits or limit warnings.

### 12.2 Allowed statements

The default allowed form is one read-only `SELECT` statement.

`WITH ... SELECT` may be supported only when the parser confirms that the complete statement remains read-only and complies with all other policy checks.

### 12.3 Rejected statements and operations

The validator must reject:

- `INSERT`.
- `UPDATE`.
- `DELETE`.
- `MERGE`.
- `DROP`.
- `ALTER`.
- `TRUNCATE`.
- `CREATE`.
- `GRANT`.
- `REVOKE`.
- Transaction-control or session-control statements that are not required for a read-only query.
- Multiple statements.
- Disallowed schemas or tables.
- Unapproved functions or constructs when the policy identifies them as unsafe.
- Statements that exceed configured limits.

The exact parser and implementation library may be selected during implementation, but regex-only validation must not be treated as sufficient for the complete policy.

### 12.4 Single-statement protection

The backend must parse the entire submitted SQL and reject multiple statements, including statements separated by semicolons or hidden in comments/formatting.

The execution layer must also use a database driver configuration that does not enable accidental multi-statement execution.

### 12.5 Dynamic table policy

Allowed schemas, tables, and columns are derived from the indexed source scope and current source metadata.

The validator must reject:

- Hallucinated tables.
- Hallucinated columns.
- Tables outside the configured source scope.
- PostgreSQL system tables unless explicitly allowed by policy.
- References to the local index database.

The validator must not rely only on the `tables_used` field returned by the model. It must inspect the actual SQL statement.

### 12.6 Resource limits

Safeguards must be configurable through application settings:

- Maximum execution time.
- Database statement timeout.
- Maximum returned rows.
- Maximum result size.
- Pagination or truncation behavior.
- Optional query complexity warnings.

The user must receive a warning or error when a result is truncated or a query may be expensive.

### 12.7 Approval and exact-SQL binding

When a query is approved, the backend should bind approval to the exact SQL version that was validated. A changed SQL string must require a new validation result.

An implementation may use an SQL hash or equivalent server-side version token. The token must be generated and checked by the backend.

### 12.8 Database-level boundary

The source PostgreSQL read-only role is the final privilege boundary. Even if application validation contains a defect, the database role must not be able to perform writes or schema changes.

### 12.9 Prompt injection and untrusted data

The application must keep these categories separate:

```text
Trusted application/system instructions
User input
Version-controlled semantic metadata
Technical schema metadata
Database values
LLM-generated SQL
```

Database values are data, not instructions. A row containing text such as "ignore previous instructions" must not alter application policy or tool permissions.

The answer stage must also treat returned database values as data and must not execute or follow instructions contained in them.

---

## 13. Review Mode and Auto Mode

### 13.1 Review Mode

Review Mode is the default.

The query must not execute until the user explicitly approves it.

The SQL Inspector must show:

- SQL text.
- Interpretation.
- Tables used.
- Assumptions.
- Validation state.
- Read-only status.
- Approved-table status.
- Multi-statement status.
- Result-limit status.
- Warnings.

Actions include:

- Edit SQL.
- Approve and execute.
- Regenerate.

### 13.2 Auto Mode

Auto Mode permits execution without an approval click only after the same deterministic validation and application policy checks pass.

Auto Mode must never:

- Bypass SQL validation.
- Bypass source role permissions.
- Execute edited SQL without revalidation.
- Remove query limits.
- Increase correction retries.

### 13.3 Regeneration

Regeneration creates a new proposal for the same query context. It must not execute automatically in Review Mode.

Regeneration should preserve:

- Query ID.
- Original question.
- Clarification context.
- Execution mode.
- Retry and regeneration telemetry.

---

## 14. Query State Machine

Each query has a query ID and an explicit lifecycle.

### 14.1 States

- `RECEIVED`.
- `ANALYZING`.
- `CLARIFICATION_REQUIRED`.
- `SCHEMA_RETRIEVED`.
- `SQL_GENERATED`.
- `VALIDATING`.
- `SQL_CORRECTION`.
- `READY_FOR_REVIEW`.
- `EDITED`.
- `APPROVED`.
- `EXECUTING`.
- `EXECUTED`.
- `ANSWER_GENERATED`.
- `COMPLETED`.
- `FAILED`.

### 14.2 Valid transitions

```text
RECEIVED -> ANALYZING
ANALYZING -> CLARIFICATION_REQUIRED
ANALYZING -> SCHEMA_RETRIEVED
CLARIFICATION_REQUIRED -> ANALYZING
SCHEMA_RETRIEVED -> SQL_GENERATED
SQL_GENERATED -> VALIDATING
VALIDATING -> SQL_CORRECTION
SQL_CORRECTION -> SQL_GENERATED
VALIDATING -> READY_FOR_REVIEW
READY_FOR_REVIEW -> EDITED
EDITED -> VALIDATING
READY_FOR_REVIEW -> APPROVED
READY_FOR_REVIEW -> EXECUTING       [validated Auto Mode]
APPROVED -> EXECUTING
EXECUTING -> EXECUTED
EXECUTED -> ANSWER_GENERATED
ANSWER_GENERATED -> COMPLETED
VALIDATING -> FAILED                [policy or retry failure]
SQL_CORRECTION -> FAILED            [retry limit exhausted]
EXECUTING -> FAILED                 [database or limit failure]
```

### 14.3 State invariants

- `CLARIFICATION_REQUIRED` contains no executable SQL.
- `READY_FOR_REVIEW` contains a validation result for the current SQL version.
- `APPROVED` refers to one exact SQL version.
- `EXECUTING` can only use SQL that passed backend validation.
- `EDITED` always returns to validation.
- `COMPLETED` contains the executed SQL and normalized result metadata.
- Failed states contain a safe user-facing error category.

---

## 15. API Contract

The frontend communicates only with FastAPI. It never connects directly to either PostgreSQL database.

### 15.1 `POST /api/query`

Purpose: start a query.

Conceptual request:

```json
{
  "question": "Which products generated the most revenue last month?",
  "execution_mode": "REVIEW"
}
```

Rules:

- `question` is required and must be bounded in size.
- `execution_mode` defaults to `REVIEW`.
- The backend creates the query ID.
- Credentials and database identifiers are not accepted from the client.

Possible responses:

- `200` or `202` with `CLARIFICATION_REQUIRED`.
- `200` or `202` with `READY_FOR_REVIEW`.
- `400` for invalid request data.
- `503` when source/index dependencies are unavailable.

### 15.2 `POST /api/query/{query_id}/clarify`

Purpose: submit clarification context.

Conceptual request:

```json
{
  "clarification": "Use total completed-order revenue."
}
```

Rules:

- The query must be in `CLARIFICATION_REQUIRED`.
- The clarification becomes user context, not a security instruction.
- The pipeline resumes analysis.

### 15.3 `POST /api/query/{query_id}/approve`

Purpose: approve a validated proposal in Review Mode.

Conceptual request:

```json
{
  "sql_version": "backend-issued version token"
}
```

If the user edited SQL, the edited SQL must be submitted through the backend and validated before approval can succeed.

### 15.4 `POST /api/query/{query_id}/execute`

Purpose: execute an approved or valid Auto Mode query.

Rules:

- Perform backend validation again.
- Do not trust frontend validation fields.
- Verify query state and exact SQL version.
- Execute only against the source database.
- Return normalized results and final answer data.

### 15.5 `POST /api/query/{query_id}/regenerate`

Purpose: request another SQL proposal.

Rules:

- Reuse the question and clarification context.
- Do not bypass validation.
- Do not execute automatically in Review Mode.

### 15.6 `GET /api/query/{query_id}`

Purpose: retrieve current query state, SQL Inspector data, result data, or safe error data.

The response must not contain:

- Database passwords.
- Full connection URLs.
- Internal stack traces.
- Unnecessary sensitive customer data.

### 15.7 `GET /api/health`

Purpose: report service and dependency health.

The health response should distinguish:

- FastAPI availability.
- Source database availability.
- Index database availability.
- Index readiness or staleness.
- OpenRouter dependency configuration without exposing secrets.

### 15.8 API response fields

Where applicable, query responses should include:

- `query_id`.
- `status`.
- `execution_mode`.
- `question`.
- `clarification` or clarification choices.
- `sql`.
- `interpretation`.
- `tables_used`.
- `assumptions`.
- `validation`.
- `warnings`.
- `result`.
- `answer`.
- `visualization` metadata.
- Safe error information.

### 15.9 Error mapping

Raw stack traces must not be exposed to normal users.

User-facing categories include:

- Invalid request.
- Clarification required.
- Schema index unavailable.
- No relevant schema found.
- Unsafe SQL rejected.
- SQL correction exhausted.
- Query limit exceeded.
- Source database unavailable.
- Query execution failed.
- Answer generation failed.

---

## 16. React Frontend Requirements

### 16.1 Required surfaces

The React application must contain:

- Query input.
- Execution mode selection.
- Clarification panel or modal.
- SQL Inspector.
- SQL editor for optional edits.
- Validation and warning display.
- Approve and execute action.
- Regenerate action.
- Results table.
- Grounded answer panel.
- Conditional visualization components.
- Basic current-session query history.

### 16.2 Query input

The input component must:

- Accept natural-language questions.
- Display loading state.
- Display backend errors safely.
- Preserve the question while clarification is requested.
- Send only API request data to FastAPI.

### 16.3 Clarification panel

The clarification UI must:

- Clearly state that the question is ambiguous.
- Show the choices or explanation returned by the backend.
- Allow the user to answer.
- Prevent execution actions while clarification is outstanding.

### 16.4 SQL Inspector

The inspector must display:

- The exact SQL proposal.
- Interpretation.
- Tables and schemas used.
- Assumptions.
- Validation results.
- Read-only status.
- Multi-statement status.
- Approved-source status.
- Resource-limit status.
- Warnings.

The edit flow must make it clear that edited SQL will be revalidated by the backend.

### 16.5 Results

The frontend must:

- Render normalized columns and rows.
- Handle empty results.
- Indicate truncation or pagination.
- Render values safely as data.
- Display the executed answer separately from SQL proposal text.

### 16.6 Query history

The MVP supports basic current-session history. It may use query IDs and frontend state rather than introducing a separate persistence system unless required by implementation.

History entries should show:

- Query ID.
- Short question.
- Status.
- Execution mode.
- Timestamp if available.

### 16.7 Frontend security

The frontend must never receive or store:

- Source database hostname.
- Source database username.
- Source database password.
- Source connection URL.
- Index database credentials.

Frontend validation indicators are informational and never authorize execution.

---

## 17. FastAPI Backend Structure

The backend must keep transport, orchestration, model calls, retrieval, security, and database access separate.

Conceptual structure:

```text
FastAPI routes
    -> Request and response schemas
    -> Query service / orchestration
    -> Deterministic LCEL workflow and controlled agent
    -> Retrieval, validation, and database services
```

Recommended repository structure:

```text
backend/
  app/
    api/
      routes/
      dependencies/
    chains/
      question_analysis.py
      schema_retrieval.py
      sql_generation.py
      sql_correction.py
      answer_generation.py
      visualization.py
    agent/
      tools.py
      controlled_agent.py
      policies.py
    retrieval/
      schema_documents.py
      semantic_metadata.py
      embeddings.py
      retriever.py
      keyword_retrieval.py
      relationship_expansion.py
      ranking.py
      index_service.py
    database/
      source_connection.py
      source_introspection.py
      source_execution.py
      index_connection.py
      index_repository.py
    security/
      sql_validation.py
      sql_parser.py
      policies.py
      limits.py
      execution_gate.py
    models/
      llm.py
      schemas.py
      state.py
    services/
      query_service.py
      indexing_service.py
      result_service.py
      telemetry_service.py
    config.py
    main.py
  tests/
    unit/
    integration/
    security/
    fixtures/
```

The exact names may change, but the responsibilities must remain separated.

### 17.1 Route responsibilities

FastAPI routes own:

- HTTP request parsing.
- Authentication/authorization hooks if added later.
- Dependency injection.
- Calling the query service.
- Mapping domain errors to HTTP responses.

Routes must not contain the complete LLM or SQL workflow.

### 17.2 Query service responsibilities

The query service owns:

- Query lifecycle.
- Orchestration.
- Mode handling.
- Tool and chain invocation.
- State persistence for the query lifecycle.
- Retry limits.
- Approval and execution gates.

### 17.3 Database service responsibilities

Database services own:

- Connection creation.
- Source introspection.
- Source execution.
- Index reads and writes.
- Timeouts and connection cleanup.

Database services must not accept connection details from the LLM or frontend.

---

## 18. LangChain and LCEL Requirements

LangChain must be used where it provides the relevant capability:

- LLM wrappers.
- Prompt templates.
- LCEL runnable composition.
- Structured output parsing.
- SQL database abstraction.
- SQL-oriented components.
- Tool interfaces.
- Retriever abstractions.
- Vector-store integration.

Application-specific code remains responsible for:

- Source schema scope.
- Security policy.
- SQL validation policy.
- Approval workflow.
- Retry policy.
- Resource limits.
- State management.
- Orchestration.
- Domain semantic metadata.

The project must not recreate LangChain's database interface, runnable composition, output parsing, or vector similarity implementation without a concrete library limitation.

The exact LangChain SQL database import must be verified against the selected package version. Conceptually:

```python
from langchain_community.utilities import SQLDatabase

source_db = SQLDatabase.from_uri(SOURCE_DATABASE_URL)
```

The connection URI remains server-side.

---

## 19. Model Configuration

### 19.1 Environment configuration

The application should support configuration similar to:

```text
OPENROUTER_API_KEY=<secret>
OPENROUTER_BASE_URL=<configured endpoint if required>
QUESTION_MODEL=<model identifier>
SQL_MODEL=<model identifier>
ANSWER_MODEL=<model identifier>
EMBEDDING_MODEL=<model identifier>
SOURCE_DATABASE_URL=<secret connection URL>
INDEX_DATABASE_URL=<local index connection URL>
SOURCE_SCHEMA_SCOPE=<configured source schema scope>
MAX_CORRECTION_RETRIES=2
MAX_REGENERATION_COUNT=<configured limit>
MAX_RETURNED_ROWS=<configured limit>
MAX_RESULT_BYTES=<configured limit>
QUERY_TIMEOUT_SECONDS=<configured limit>
LOG_LEVEL=<configured level>
```

Names may be adjusted to match the configuration library, but the separation of roles and secrets must remain.

### 19.2 Model roles

Logical roles are:

- Question analysis.
- SQL generation.
- SQL correction.
- Answer generation.
- Embedding generation.

The MVP may map multiple roles to one OpenRouter model. The code must use role-based configuration so models can be replaced without changing the workflow graph.

Model IDs shown in the flow diagram are defaults/examples only and must not be hardcoded as application policy.

### 19.3 LLM output handling

All model output is untrusted and must be:

- Parsed.
- Validated against a structured schema.
- Checked for missing fields.
- Checked for unexpected content where relevant.
- Sent through deterministic policy checks before execution.

---

## 20. Observability

### 20.1 MVP approach

Use structured application logging in FastAPI. Do not create a separate proxy service for logging and do not require LangSmith.

### 20.2 Query telemetry

Each query should record, where available:

- `query_id`.
- `user_question` or a privacy-safe representation.
- `execution_mode`.
- Selected schemas and tables.
- Retrieved schema items.
- Source/index fingerprints.
- Model role.
- Model identifier.
- Schema retrieval latency.
- SQL generation latency.
- Validation result.
- Validation failure category.
- Retry count.
- Execution latency.
- Row count.
- Result truncation state.
- Answer generation latency.
- Final status.

### 20.3 Logging safety

Logs must not contain:

- Database credentials.
- Connection URLs with secrets.
- Unnecessary full customer records.
- Unnecessary sensitive database values.

If SQL text is logged for debugging, it must be subject to the project's data-sensitivity policy. Query hashes and structural metadata should be preferred for normal telemetry.

### 20.4 Stage measurement

Measure pipeline stages independently so latency can be attributed to:

- Analysis.
- Embedding.
- Vector retrieval.
- Metadata retrieval.
- Relationship expansion.
- SQL generation.
- Validation.
- Correction.
- Database execution.
- Answer generation.

---

## 21. Error Handling

### 21.1 Ambiguous question

User-facing message:

```text
I need one clarification before I can query the database.

What should "best customers" mean here?
- Highest total spending
- Most orders
- Most recent activity
```

No SQL is generated until the ambiguity is resolved.

### 21.2 Unsafe SQL

User-facing message:

```text
The query was rejected because it contains an operation that is not allowed.
```

The response may include a safe explanation such as write operation, disallowed table, multiple statements, or limit violation.

### 21.3 Correction exhausted

User-facing message:

```text
I couldn't generate a valid query after two correction attempts.
Please rephrase the question.
```

### 21.4 Source database failure

User-facing message:

```text
The database query could not be executed.
Please try again.
```

Internal logs may contain diagnostic details subject to privacy policy.

### 21.5 Index failure

User-facing message:

```text
The schema index is not available yet. Please run schema indexing or try again later.
```

### 21.6 Empty or unsupported result

The application must distinguish:

- Valid query with zero rows.
- Valid query with truncated results.
- Query that exceeded a limit.
- Query whose result shape cannot produce a chart.

---

## 22. Testing Strategy

### 22.1 Unit tests

Unit-test:

- Request validation.
- Structured model output parsing.
- Ambiguity classification behavior.
- Schema document construction.
- Relationship expansion bounds.
- Retrieval result merging and ranking.
- SQL statement policy.
- Single-statement detection.
- Read-only enforcement.
- Dynamic approved-table checks.
- Resource-limit checks.
- Execution-state checks.
- Exact-SQL/version binding.
- Two-retry correction behavior.
- Result normalization.
- Chart-shape selection.
- Error mapping.

### 22.2 Security tests

Security tests must prove that:

- `INSERT` is rejected.
- `UPDATE` is rejected.
- `DELETE` is rejected.
- DDL is rejected.
- `GRANT` and `REVOKE` are rejected.
- Multi-statement SQL is rejected.
- SQL hidden in comments or formatting is handled safely.
- Hallucinated tables are rejected.
- Hallucinated columns are rejected.
- Index database references are rejected as execution targets.
- Edited unsafe SQL is rejected.
- Frontend validation fields cannot authorize execution.
- Auto Mode cannot bypass validation.
- The agent cannot supply or change a database connection.
- Database values containing prompt-injection text do not change tool permissions.

### 22.3 Integration tests

Use a disposable or dedicated PostgreSQL test database to verify:

- Source introspection.
- Source schema fingerprinting.
- Schema document generation.
- Index writes.
- Vector and metadata retrieval.
- Source read-only query execution.
- Timeout and result-limit behavior.
- Connection separation between source and index databases.

The test database may have representative fixture schemas and data. Those fixtures are not part of the production application schema.

### 22.4 API tests

Test:

- New query.
- Ambiguous query.
- Clarification submission.
- Valid Review Mode query.
- Approval.
- Edited SQL.
- Edited unsafe SQL.
- Auto Mode query.
- Regeneration.
- Correction exhaustion.
- Source database failure.
- Index failure.
- Query lookup.
- Health endpoint.

### 22.5 Frontend tests

Test:

- Query submission.
- Loading and error states.
- Clarification rendering.
- SQL Inspector rendering.
- SQL editing flow.
- Approval flow.
- Auto Mode display.
- Table rendering.
- Empty and truncated results.
- Conditional chart rendering.
- Session history.

### 22.6 End-to-end tests

At least one end-to-end test must verify the complete path:

```text
Question
  -> Retrieval from local index
  -> SQL proposal
  -> Validation
  -> Review approval
  -> Execution against source PostgreSQL
  -> Result table
  -> Grounded answer
```

At least one end-to-end test must verify that editing the SQL causes backend revalidation before execution.

---

## 23. Evaluation Strategy

Evaluation is a first-class project feature, not only a final manual demo.

### 23.1 Dataset size

Create approximately 50-100 benchmark questions for the MVP.

The questions must be tied to a known test database schema and expected concepts/results. The schema may be a test fixture and does not define the production source schema.

### 23.2 Evaluation categories

Include:

- Simple lookup.
- Filtering.
- Aggregation.
- Sorting.
- Joins.
- Date/time analysis.
- Multi-table analysis.
- Nested queries.
- Ambiguous questions.
- Impossible questions.
- Unsafe requests.
- Adversarial prompts.

### 23.3 Evaluation case fields

Each case should define, where applicable:

- Question.
- Clarification expectation.
- Expected source tables.
- Expected columns or concepts.
- Expected relationships.
- Expected filters.
- Expected grouping.
- Expected ordering.
- Expected result or result properties.
- Whether the request is unsafe.
- Whether the request is impossible.

### 23.4 Metrics

Report:

- SQL validity: percentage of generated SQL that executes successfully.
- SQL safety: percentage of unsafe SQL correctly rejected.
- Schema retrieval recall: whether relevant tables and columns were retrieved.
- Schema precision: amount of irrelevant context included.
- Relationship accuracy: whether required relationships were surfaced.
- Semantic correctness: whether SQL matches intended meaning.
- Result correctness: whether values match expected results.
- Clarification accuracy: whether ambiguity is correctly identified.
- Answer faithfulness: whether the answer matches executed results.
- Latency by pipeline stage.

### 23.5 Evaluation example

```text
Question:
Which five customers spent the most in 2026?

Expected concepts:
- Identify the customer entity.
- Identify the spending metric.
- Join the required source tables.
- Filter the requested time period.
- Aggregate by customer.
- Sort descending.
- Return five rows.
```

Evaluation must inspect both structural SQL properties and actual returned results where possible.

---

## 24. Configuration and Secret Management

### 24.1 Secret rules

Secrets must not be committed to source control.

`.env.example` may contain placeholders only.

Secrets must be provided through environment variables or Docker secrets in non-development environments.

### 24.2 Secret locations

Only the backend may access:

- OpenRouter API key.
- Source database connection URL.
- Index database connection URL.

React and model prompts must never receive these values.

### 24.3 Configuration validation

Startup or health checks should report missing required configuration without printing secret values.

The backend should fail clearly when:

- Source URL is missing.
- Index URL is missing.
- OpenRouter key is missing for an LLM-dependent operation.
- Model role is missing.
- Required query limits are invalid.

---

## 25. Repository and Documentation Requirements

Recommended top-level structure:

```text
project/
  backend/
  frontend/
  schema_index/
    metadata/
    scripts/
  evaluation/
    datasets/
    runners/
    reports/
  tests/
    fixtures/
  docs/
    architecture.md
    security.md
    retrieval.md
    evaluation.md
    PLAN.md
    TASKS.md
  Flow Diagram/
  docker-compose.yml
  .env.example
  README.md
```

There must not be a production `database/migrations` or `database/seed` directory that implies the application owns a fixed business schema. Test fixture database setup may live under tests and must be clearly isolated.

### 25.1 Architecture documentation

Document:

- External source database connection.
- Local index database.
- Query pipeline.
- Controlled agent boundaries.
- SQL validation boundary.
- Review and Auto Modes.
- Source read-only role.
- Data flow between source and index.

### 25.2 Security documentation

Document:

- Credential handling.
- Source role permissions.
- Validator policy.
- Edited SQL revalidation.
- Prompt-injection separation.
- Resource limits.
- Logging restrictions.

### 25.3 Retrieval documentation

Document:

- Introspection fields.
- Semantic metadata.
- Document formats.
- Embedding process.
- Hybrid retrieval.
- Relationship expansion.
- Ranking and compact context.
- Index refresh behavior.

### 25.4 README requirements

The README should explain:

- What the project does.
- Why it is safe by design.
- How to configure a source PostgreSQL URL.
- How to start the local services.
- How to run schema indexing.
- How to run the frontend and backend.
- How Review Mode and Auto Mode differ.
- How to run tests and evaluation.
- What is intentionally out of scope.

---

## 26. MVP Definition of Done

### Product behavior

- [ ] The project is clearly identified as a safe, schema-aware natural-language-to-SQL analytics platform.
- [ ] A user can submit a natural-language question.
- [ ] Ambiguous questions request clarification instead of guessing.
- [ ] Clear questions proceed to schema retrieval.
- [ ] Review Mode is the default.
- [ ] Auto Mode is available only with deterministic validation.
- [ ] The SQL Inspector exposes SQL, interpretation, tables, assumptions, validation, and warnings.
- [ ] Users can edit SQL in Review Mode.
- [ ] Edited SQL is revalidated by the backend.
- [ ] Results display as a table.
- [ ] Suitable results display a chart.
- [ ] Results receive a grounded natural-language explanation.

### Source database and indexing

- [ ] The application accepts a backend-only real PostgreSQL connection URL.
- [ ] The same source database is used for introspection and read-only query execution.
- [ ] No fixed business table list is required by the application.
- [ ] The source database business schema is not created, migrated, seeded, or modified.
- [ ] Technical metadata is extracted from the source database.
- [ ] Version-controlled semantic metadata is supported.
- [ ] Technical and semantic metadata produce rich schema documents.
- [ ] Schema documents are embedded before runtime queries.
- [ ] Documents and embeddings are stored in a separate local PostgreSQL + pgvector index.
- [ ] The index process is repeatable and avoids uncontrolled duplicates.
- [ ] The source schema scope excludes unintended system schemas.
- [ ] Index freshness or readiness is observable.

### Agent and LangChain

- [ ] LangChain is used for model, SQL, structured-output, tool, and retrieval functionality where appropriate.
- [ ] LCEL is used for the core application workflow.
- [ ] The controlled agent can use only bounded application tools.
- [ ] `get_relevant_schema` reads the local index.
- [ ] `generate_sql` returns structured proposals.
- [ ] `execute_readonly_sql` targets only the source database.
- [ ] The agent receives no credentials.
- [ ] The agent cannot bypass application state or validation.
- [ ] Model IDs are configuration-driven and replaceable.

### Retrieval

- [ ] Semantic vector retrieval is implemented.
- [ ] Keyword or metadata retrieval is implemented.
- [ ] Retrieval signals are combined.
- [ ] Relationship expansion is bounded.
- [ ] Schema candidates are ranked and filtered.
- [ ] SQL generation receives compact relevant schema context.
- [ ] Business rows are not embedded for primary schema retrieval.

### SQL safety

- [ ] Only one read-only `SELECT` is allowed by default.
- [ ] Carefully validated `WITH ... SELECT` support is implemented if enabled.
- [ ] Writes and DDL are rejected.
- [ ] Multi-statement queries are rejected.
- [ ] Tables and columns outside the approved introspected source scope are rejected.
- [ ] Suspicious or unsupported constructs are handled by policy.
- [ ] Execution timeout is enforced.
- [ ] Row and result-size limits are enforced.
- [ ] Truncation or pagination is represented in results.
- [ ] Correction is limited to two attempts.
- [ ] Review Mode requires explicit approval.
- [ ] Auto Mode still validates SQL.
- [ ] Every execution endpoint revalidates the exact SQL.
- [ ] PostgreSQL runtime permissions are read-only.

### API and frontend

- [ ] Required query, clarification, approval, execution, regeneration, lookup, and health endpoints exist.
- [ ] The API makes execution mode explicit.
- [ ] The frontend communicates only with FastAPI.
- [ ] The frontend never receives database credentials.
- [ ] Raw backend stack traces are not shown to normal users.
- [ ] Current-session query history is available.

### Observability

- [ ] Every query has a query ID.
- [ ] Query stage telemetry is structured.
- [ ] Validation result and retry count are recorded.
- [ ] Execution and answer latencies are recorded.
- [ ] Final status and row count are recorded.
- [ ] Credentials and unnecessary sensitive customer data are not logged.
- [ ] The MVP does not require a separate proxy or LangSmith.

### Testing and evaluation

- [ ] Unit tests cover validation and workflow policy.
- [ ] Security tests cover unsafe, multi-statement, edited, and hallucinated SQL.
- [ ] Integration tests cover source introspection and local indexing.
- [ ] End-to-end tests cover approval and source execution.
- [ ] An evaluation set of approximately 50-100 questions exists.
- [ ] Evaluation covers normal, ambiguous, impossible, unsafe, and adversarial questions.
- [ ] Quality metrics are reported.

### Reproducibility and documentation

- [ ] Docker Compose starts the frontend, backend, and local index database.
- [ ] Persistent storage is configured for the local index database.
- [ ] `.env.example` contains placeholders only.
- [ ] Local setup instructions exist.
- [ ] Architecture and security documentation exist.
- [ ] The source database and local index database responsibilities are documented.

---

## 27. Requirement Traceability

| PRD requirement | Implementation location in this plan |
|---|---|
| Natural-language querying | Sections 3, 5, 11, 15, 16 |
| Never guess ambiguity | Sections 3.2, 5.3, 11.3, 11.4, 21 |
| Schema-aware retrieval | Sections 3.3, 8, 9 |
| Read-only execution | Sections 3.4, 7, 12 |
| SQL transparency | Sections 3.5, 13, 15, 16 |
| Replaceable models | Sections 3.6, 19 |
| LangChain and LCEL | Sections 1.4, 10, 11, 18 |
| Controlled tools | Section 10 |
| Schema ingestion | Section 8 |
| Hybrid retrieval | Section 9 |
| SQL correction | Sections 11.6, 14, 26 |
| Review Mode | Section 13.1 |
| Auto Mode | Section 13.2 |
| Edited SQL security | Sections 5.6, 12.7, 26 |
| Query limits | Section 12.6 |
| Result processing | Section 11.7 |
| Answer generation | Section 11.7 |
| Visualization | Section 11.8, 16.5 |
| API surface | Section 15 |
| State machine | Section 14 |
| Prompt injection defense | Section 12.9 |
| Observability | Section 20 |
| Evaluation | Section 23 |
| Error handling | Section 21 |
| Repository structure | Section 17, 25 |
| Security documentation | Section 25.2 |
| Local reproducibility | Sections 6.2, 24, 25 |

---

## 28. Deferred Enhancements

The following remain outside the MVP unless a later decision changes scope:

- Explicit semantic metric layer for concepts such as revenue, active customer, completed order, refunded order, and delivered shipment.
- Query plans and cost explanations.
- LangSmith tracing and evaluation integration.
- Model routing based on measured performance.
- Published embedding versus keyword versus hybrid retrieval benchmark.
- User feedback loops for incorrect SQL, interpretation, or answer.
- More advanced authorization and multi-user tenancy.
- More database engines.
- Autonomous agent behavior beyond bounded tools.
- Production managed PostgreSQL deployment changes.

Deferred features must not weaken deterministic safeguards or read-only database permissions.

---

## 29. Final Quality Principle

The MVP optimizes for trustworthy answers, not merely syntactically valid SQL.

```text
Correct question understanding
  + Relevant schema retrieval
  + Correct relationships
  + Correct SQL
  + Safe execution
  + Correct result interpretation
  = Trustworthy answer
```

Every major stage must remain inspectable, testable, replaceable, and measurable.
