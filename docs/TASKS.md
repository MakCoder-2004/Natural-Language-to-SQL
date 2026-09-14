# Natural Language to SQL - Implementation Tasks

This document is the implementation checklist for the MVP described in
`PLAN.md`. It converts the requirements into ordered, actionable milestones.

## Source Documents

- `PLAN.md` is the authoritative implementation specification.
- This file is the implementation tracker and milestone status record.

## Status Legend

- `[ ]` Not started.
- `[~]` In progress.
- `[x]` Completed.
- `[-]` Cancelled or intentionally deferred.

## Global Rules

- [ ] Keep the source database external to the application.
- [ ] Use the same source PostgreSQL database for introspection and read-only query execution.
- [ ] Use a separate local PostgreSQL database with pgvector for the schema index.
- [ ] Do not create, migrate, seed, or modify a fixed business schema in the source database.
- [ ] Keep source database credentials, index credentials, and model API keys on the backend only.
- [ ] Keep deterministic SQL validation outside the LLM and controlled agent.
- [ ] Revalidate the exact SQL at every execution boundary.
- [ ] Keep Review Mode as the default execution mode.
- [ ] Ensure Auto Mode cannot bypass validation or resource limits.
- [ ] Do not embed business rows for primary schema retrieval.
- [ ] Keep model IDs and model roles configuration-driven.
- [ ] Keep the controlled agent limited to bounded application tools.
- [ ] Keep production business migrations and seed directories out of the repository.
- [ ] Use isolated test fixtures when representative tables and data are needed for tests.

## Dependency Order

Milestones should normally be completed in this order:

1. Project foundation.
2. Source database connection and introspection.
3. Schema documentation and indexing.
4. Hybrid schema retrieval.
5. Basic SQL pipeline.
6. Deterministic LCEL workflow and controlled agent.
7. SQL safety and correction.
8. Review and approval workflow.
9. FastAPI backend API.
10. React UI and components.
11. Model replaceability.
12. Observability, testing, and evaluation.
13. Portfolio polish and release.

Milestones may be developed in parallel when their dependencies are satisfied,
but a milestone is not complete until its exit criteria and tests are complete.

---

## Milestone 1 - Project Foundation

### Objective

Establish the repository, runtime structure, local development environment, and
configuration boundaries without creating a fixed business database schema.

### Dependencies

- None.

### Deliverable

A runnable project skeleton with backend, frontend, local index database, safe
configuration handling, and initial health reporting.

### Checklist

- [ ] Create the `backend/` directory and application package structure.
- [ ] Create the `frontend/` directory and application package structure.
- [ ] Create `schema_index/metadata/` and `schema_index/scripts/` directories.
- [ ] Create `evaluation/datasets/`, `evaluation/runners/`, and `evaluation/reports/` directories.
- [ ] Create `tests/fixtures/` and keep fixture database setup isolated from production code.
- [ ] Create documentation directories for architecture, security, retrieval, and evaluation.
- [ ] Configure the backend language version and dependency management.
- [ ] Configure the frontend runtime, package manager, and dependency management.
- [ ] Add formatting, linting, type-checking, and test commands for the backend.
- [ ] Add formatting, linting, type-checking, and test commands for the frontend.
- [ ] Add `.env.example` containing placeholders only.
- [ ] Define `SOURCE_DATABASE_URL` configuration.
- [ ] Define `INDEX_DATABASE_URL` configuration.
- [ ] Define OpenRouter API key and model-role configuration.
- [ ] Define query timeout, returned-row, result-byte, and correction-retry limits.
- [ ] Define source schema scope configuration.
- [ ] Add Docker Compose for the backend, frontend, and local pgvector database.
- [ ] Do not add a source business database container, business migrations, or business seed data.
- [ ] Add initial backend startup configuration validation.
- [ ] Add an initial `/api/health` endpoint or health placeholder.
- [ ] Document the external source database and local index database responsibilities.
- [ ] Document local startup commands.

### Exit Criteria

- [ ] Local services start successfully with documented commands.
- [ ] Missing required configuration produces safe, actionable errors.
- [ ] No application code assumes tables such as `customers`, `orders`, or `products`.
- [ ] No secrets are committed.

---

## Milestone 2 - Source Database Connection and Introspection

### Objective

Connect to the existing PostgreSQL source database and inspect its actual schema
dynamically.

### Dependencies

- Milestone 1.

### Deliverable

A source database service that can connect, verify read-only access, introspect
the configured schema scope, and generate a stable schema fingerprint.

### Checklist

- [ ] Implement a dedicated source database connection service.
- [ ] Implement a separate index database connection service.
- [ ] Make source and index connection dependencies explicit and typed.
- [ ] Verify source and index connections cannot be accidentally swapped.
- [ ] Integrate LangChain's PostgreSQL SQL abstraction where appropriate.
- [ ] Configure source connection pooling and cleanup.
- [ ] Configure connection and query timeouts.
- [ ] Implement configurable source schema scope filtering.
- [ ] Exclude unintended PostgreSQL system schemas from the source scope.
- [ ] Introspect source schemas and namespaces.
- [ ] Introspect tables and views in the approved source scope.
- [ ] Introspect columns, data types, nullability, defaults, and comments.
- [ ] Introspect primary keys and unique constraints.
- [ ] Introspect foreign keys and relationship metadata.
- [ ] Introspect relevant indexes and ordering information.
- [ ] Generate a stable source schema fingerprint.
- [ ] Verify the source connection is used for both introspection and query execution.
- [ ] Document the required read-only source database role.
- [ ] Verify that the source role cannot write or alter schema objects.
- [ ] Add connection failure and permission failure handling.
- [ ] Add integration tests against a disposable or dedicated PostgreSQL test database.

### Exit Criteria

- [ ] The backend can inspect an arbitrary supported source PostgreSQL database.
- [ ] Introspection returns enough metadata for document generation and SQL validation.
- [ ] The application does not modify, migrate, or seed the source database.
- [ ] Source and index connections remain isolated.

---

## Milestone 3 - Schema Documentation and Indexing

### Objective

Convert discovered technical metadata and optional semantic metadata into
searchable schema documents stored in the local pgvector index.

### Dependencies

- Milestone 2.

### Deliverable

A repeatable schema indexing pipeline:

```text
Source metadata + semantic metadata
    -> schema documents
    -> embeddings
    -> local PostgreSQL + pgvector index
```

### Checklist

- [ ] Define the versioned semantic metadata format.
- [ ] Support descriptions for discovered schemas, tables, columns, and relationships.
- [ ] Ensure semantic metadata can describe arbitrary source identifiers.
- [ ] Define metadata behavior for missing or stale semantic descriptions.
- [ ] Build schema documents from technical metadata.
- [ ] Include qualified identifiers, types, constraints, relationships, and descriptions.
- [ ] Include source fingerprint and document version in every indexed document.
- [ ] Define document categories for tables, columns, relationships, and semantic concepts.
- [ ] Enable the pgvector extension in the local index database.
- [ ] Define local index tables for documents, embeddings, metadata, and index runs.
- [ ] Keep local index schema initialization separate from source business schema management.
- [ ] Implement embedding generation through the configured embedding model.
- [ ] Implement idempotent document upsert behavior.
- [ ] Store source fingerprints and indexing timestamps.
- [ ] Store embedding model identifiers and document versions.
- [ ] Implement a repeatable indexing command or script.
- [ ] Implement index refresh behavior for source schema changes.
- [ ] Implement index readiness and freshness checks.
- [ ] Report indexing failures without exposing secrets.
- [ ] Add tests for document generation and semantic metadata merging.
- [ ] Add tests for repeat indexing and stale-document replacement.
- [ ] Add integration tests for pgvector writes and reads.

### Exit Criteria

- [ ] A real source schema can be indexed without hardcoded business tables.
- [ ] Re-running indexing does not create uncontrolled duplicates.
- [ ] The local index contains searchable documents and embeddings.
- [ ] Index readiness and source freshness are observable.

---

## Milestone 4 - Hybrid Schema Retrieval

### Objective

Retrieve compact, relevant schema context for each natural-language question.

### Dependencies

- Milestone 3.

### Deliverable

A bounded retrieval service combining semantic, keyword, metadata, and
relationship signals.

### Checklist

- [ ] Implement semantic vector retrieval from the local index.
- [ ] Implement keyword or metadata retrieval from the local index.
- [ ] Combine retrieval signals using explicit ranking logic.
- [ ] Make retrieval limits configurable.
- [ ] Implement table and column candidate ranking.
- [ ] Implement bounded foreign-key relationship expansion.
- [ ] Include nearby tables and columns only when justified by retrieved candidates.
- [ ] Include semantic descriptions in ranking and final context.
- [ ] Remove duplicate documents and redundant metadata.
- [ ] Produce a compact structured retrieval result.
- [ ] Include source fingerprint and retrieval diagnostics in the result.
- [ ] Handle an empty or unavailable index safely.
- [ ] Return a clear index-readiness error when runtime retrieval is impossible.
- [ ] Add retrieval latency measurements.
- [ ] Add tests for keyword retrieval.
- [ ] Add tests for vector retrieval.
- [ ] Add tests for signal merging and ranking.
- [ ] Add tests for relationship expansion bounds.
- [ ] Add tests proving retrieval does not return uncontrolled full-schema context.

### Exit Criteria

- [ ] Relevant source schema context is returned for arbitrary supported questions.
- [ ] Both vector and non-vector retrieval signals are used.
- [ ] Relationship expansion is bounded and deterministic.
- [ ] SQL generation receives compact relevant context rather than the full database.

---

## Milestone 5 - Basic SQL Pipeline

### Objective

Build the first working backend vertical slice from a natural-language question
to a validated result.

### Dependencies

- Milestone 2.
- Milestone 4.

### Deliverable

A basic pipeline:

```text
Question -> schema retrieval -> SQL generation -> validation -> execution -> result
```

### Checklist

- [ ] Define request, response, and internal domain models.
- [ ] Define the query ID and query lifecycle identifiers.
- [ ] Implement natural-language question input handling.
- [ ] Implement initial SQL generation using LangChain.
- [ ] Define structured SQL proposal output.
- [ ] Include interpretation, tables, assumptions, warnings, and SQL in proposals.
- [ ] Connect SQL generation to retrieved schema context.
- [ ] Define a validation service interface before implementing pipeline execution.
- [ ] Route generated SQL through the validation service.
- [ ] Route execution only through the source database service.
- [ ] Normalize returned columns and rows.
- [ ] Represent empty results distinctly from failures.
- [ ] Represent truncation and result limits in responses.
- [ ] Generate a grounded answer from executed results.
- [ ] Generate a basic visualization selection result.
- [ ] Add safe handling for model, validation, index, and database failures.
- [ ] Add a backend integration test for a successful clear question.
- [ ] Add an integration test for a valid query returning zero rows.
- [ ] Verify there is no execution path that bypasses validation.

### Exit Criteria

- [ ] A clear question can produce a validated read-only query and normalized result.
- [ ] The answer is based on executed data, not generated claims.
- [ ] Empty and truncated results are represented correctly.
- [ ] The pipeline uses the external source database and local schema index correctly.

---

## Milestone 6 - Deterministic LCEL Workflow and Controlled Agent

### Objective

Formalize orchestration with LCEL and keep model behavior within bounded
application controls.

### Dependencies

- Milestone 4.
- Milestone 5.

### Deliverable

A state-driven LCEL workflow with a controlled agent and bounded tools.

### Checklist

- [ ] Define the complete query state model.
- [ ] Define valid query states and allowed transitions.
- [ ] Implement structured question analysis.
- [ ] Detect ambiguity before SQL generation.
- [ ] Define clarification choices and clarification state.
- [ ] Prevent SQL generation while clarification is outstanding.
- [ ] Compose analysis, retrieval, generation, validation, execution, and answer stages with LCEL.
- [ ] Implement bounded `get_relevant_schema`.
- [ ] Implement bounded `generate_sql`.
- [ ] Implement bounded `execute_readonly_sql`.
- [ ] Ensure `get_relevant_schema` reads only the local index.
- [ ] Ensure `execute_readonly_sql` targets only the source database.
- [ ] Ensure tools receive no credentials or connection details.
- [ ] Ensure the agent cannot mutate workflow state or bypass gates.
- [ ] Limit the agent to approved application tools.
- [ ] Add structured model-output parsing and missing-field validation.
- [ ] Implement regeneration behavior through the workflow state.
- [ ] Implement graceful handling for impossible and unsupported questions.
- [ ] Add tests for valid questions and state transitions.
- [ ] Add tests for ambiguous questions.
- [ ] Add tests for impossible questions.
- [ ] Add tests proving the agent cannot access credentials or arbitrary connections.

### Exit Criteria

- [ ] The core workflow is composable, state-driven, and inspectable.
- [ ] Ambiguous questions stop before SQL generation.
- [ ] The controlled agent cannot directly access databases or secrets.
- [ ] The workflow has no hidden execution route outside the application gates.

---

## Milestone 7 - SQL Safety and Correction

### Objective

Establish defense-in-depth protection for generated and user-edited SQL.

### Dependencies

- Milestone 5.
- Milestone 6.

### Deliverable

A deterministic SQL validation, resource-limiting, correction, and execution
policy enforced independently of the model.

### Checklist

- [ ] Allow one read-only `SELECT` statement by default.
- [ ] Add carefully validated `WITH ... SELECT` support if enabled.
- [ ] Reject `INSERT`, `UPDATE`, `DELETE`, and `MERGE`.
- [ ] Reject DDL statements.
- [ ] Reject transaction control statements.
- [ ] Reject `GRANT`, `REVOKE`, and other privilege operations.
- [ ] Reject multi-statement SQL.
- [ ] Detect hidden statements in comments and formatting.
- [ ] Validate referenced schemas against the approved source scope.
- [ ] Validate referenced tables against introspected source metadata.
- [ ] Validate referenced columns against introspected source metadata.
- [ ] Reject references to the local index database.
- [ ] Define and enforce suspicious or unsupported construct policy.
- [ ] Enforce statement timeouts.
- [ ] Enforce returned-row limits.
- [ ] Enforce result byte limits.
- [ ] Represent truncation and pagination in results.
- [ ] Implement a maximum of two correction attempts.
- [ ] Pass validation errors to correction without exposing unnecessary sensitive data.
- [ ] Revalidate the exact SQL at every execution endpoint.
- [ ] Bind approval to the SQL version or hash.
- [ ] Verify the PostgreSQL runtime role is read-only.
- [ ] Add unit tests for every statement policy category.
- [ ] Add security tests for multi-statement and comment-obfuscated SQL.
- [ ] Add security tests for hallucinated tables and columns.
- [ ] Add security tests for index database references.
- [ ] Add tests for timeouts, row limits, bytes limits, and correction exhaustion.

### Exit Criteria

- [ ] Unsafe SQL is rejected deterministically.
- [ ] Correction cannot loop indefinitely.
- [ ] Edited SQL cannot bypass backend validation.
- [ ] Database permissions provide an independent safety boundary.

---

## Milestone 8 - Review and Approval Workflow

### Objective

Make Review Mode the default transparent execution experience while retaining a
validated Auto Mode.

### Dependencies

- Milestone 6.
- Milestone 7.

### Deliverable

A complete query review lifecycle with proposal inspection, safe editing,
approval, revalidation, and execution gates.

### Checklist

- [ ] Implement Review Mode as the default execution mode.
- [ ] Add explicit Auto Mode support.
- [ ] Require approval before Review Mode execution.
- [ ] Prevent approval when validation fails.
- [ ] Store the exact proposed SQL and current SQL version.
- [ ] Support SQL editing in Review Mode.
- [ ] Revalidate edited SQL on the backend.
- [ ] Invalidate stale approvals after SQL edits.
- [ ] Display interpretation, assumptions, tables, validation, and warnings.
- [ ] Display read-only status.
- [ ] Display approved-source status.
- [ ] Display multi-statement status.
- [ ] Display resource-limit status.
- [ ] Implement safe regeneration.
- [ ] Preserve the original natural-language question through clarification and review.
- [ ] Add tests for approval and execution gates.
- [ ] Add tests for edited valid SQL.
- [ ] Add tests for edited unsafe SQL.
- [ ] Add tests for stale approvals.
- [ ] Add tests proving Auto Mode still validates SQL.

### Exit Criteria

- [ ] Review Mode cannot execute without explicit approval.
- [ ] Auto Mode performs deterministic validation before execution.
- [ ] The executed SQL is exactly the SQL that was validated and approved.
- [ ] Regeneration does not silently execute a new proposal.

---

## Milestone 9 - FastAPI Backend API

### Objective

Expose the query workflow through a stable, safe FastAPI backend API. This
milestone owns transport and backend API behavior, not React presentation.

### Dependencies

- Milestone 8.
- Milestone 1 configuration and health foundation.

### Deliverable

A documented FastAPI API that exposes the query lifecycle while keeping routes
thin and delegating work to application services.

### Checklist

- [ ] Create FastAPI application entrypoint and dependency wiring.
- [ ] Create request and response schemas for all public endpoints.
- [ ] Implement `POST /api/query`.
- [ ] Implement `POST /api/query/{query_id}/clarify`.
- [ ] Implement `POST /api/query/{query_id}/approve`.
- [ ] Implement `POST /api/query/{query_id}/execute`.
- [ ] Implement `POST /api/query/{query_id}/regenerate`.
- [ ] Implement `GET /api/query/{query_id}`.
- [ ] Implement `GET /api/health`.
- [ ] Make execution mode explicit in API requests and responses.
- [ ] Return query IDs for query lifecycle operations.
- [ ] Return clarification data without generating SQL prematurely.
- [ ] Return SQL Inspector data in structured response fields.
- [ ] Return normalized result columns, rows, limits, and truncation state.
- [ ] Return grounded answer and optional visualization data separately from SQL text.
- [ ] Add request validation for malformed or incomplete payloads.
- [ ] Map domain errors to safe HTTP responses.
- [ ] Map ambiguous, unsafe, correction-exhausted, database, and index failures distinctly.
- [ ] Ensure raw backend stack traces are not returned to normal users.
- [ ] Ensure routes do not contain the complete LLM or SQL workflow.
- [ ] Add dependency injection for query, indexing, database, model, and telemetry services.
- [ ] Add CORS configuration for the local frontend.
- [ ] Add API documentation for request and response contracts.
- [ ] Add API tests for clear, ambiguous, impossible, unsafe, and failed queries.
- [ ] Add API tests for approval, execution, regeneration, lookup, and health.
- [ ] Add API tests proving every execution request revalidates exact SQL.
- [ ] Add API tests proving frontend-provided validation cannot authorize execution.

### Exit Criteria

- [ ] Every required API endpoint exists and has a tested contract.
- [ ] FastAPI routes delegate to backend services instead of containing orchestration logic.
- [ ] API responses are safe, structured, and sufficient for the frontend.
- [ ] No database credentials or connection details appear in API responses.

---

## Milestone 10 - React UI and Components

### Objective

Build the user-facing React experience for querying, clarification, SQL review,
execution, results, visualization, and current-session history.

### Dependencies

- Milestone 9.
- Milestone 8 workflow behavior.

### Deliverable

A responsive React application that communicates only with FastAPI and supports
the complete Review Mode and Auto Mode journeys.

### Checklist

- [ ] Create the React application shell and route structure.
- [ ] Create a typed or validated FastAPI API client.
- [ ] Implement natural-language query input.
- [ ] Preserve the question while clarification is requested.
- [ ] Implement loading states for every asynchronous query action.
- [ ] Implement safe user-facing error states.
- [ ] Implement execution mode selection with Review Mode as the default.
- [ ] Implement clarification panel or modal.
- [ ] Disable execution actions while clarification is outstanding.
- [ ] Implement SQL Inspector component.
- [ ] Display exact SQL proposal.
- [ ] Display interpretation, assumptions, tables, validation, and warnings.
- [ ] Display read-only, source-scope, multi-statement, and resource-limit status.
- [ ] Implement SQL editor for Review Mode.
- [ ] Clearly state that edited SQL is revalidated by the backend.
- [ ] Implement approve and execute actions.
- [ ] Implement regeneration action.
- [ ] Implement results table with normalized columns and rows.
- [ ] Implement empty-result state.
- [ ] Implement truncation and pagination indication.
- [ ] Render returned values safely as data.
- [ ] Implement grounded answer panel separate from SQL proposal text.
- [ ] Implement conditional chart components for suitable result shapes.
- [ ] Implement current-session query history.
- [ ] Show query ID, short question, status, execution mode, and timestamp when available.
- [ ] Prevent frontend-only validation indicators from authorizing execution.
- [ ] Ensure the frontend never receives or stores database credentials.
- [ ] Ensure the frontend communicates only with FastAPI.
- [ ] Make the main workflow usable on desktop and mobile layouts.
- [ ] Add component tests for query input, loading, errors, clarification, and SQL Inspector.
- [ ] Add component tests for editing, approval, Auto Mode, and regeneration.
- [ ] Add component tests for table, empty, truncated, and chart results.
- [ ] Add component tests for current-session history.
- [ ] Add a frontend integration test for the primary Review Mode journey.

### Exit Criteria

- [ ] A user can complete the full query, clarification, review, approval, execution, and answer flow.
- [ ] Auto Mode is visible and understandable without weakening backend safeguards.
- [ ] The UI handles loading, empty, truncated, validation, and failure states.
- [ ] The application works on desktop and mobile layouts.

---

## Milestone 11 - Model Replaceability

### Objective

Make all model choices configuration-driven and replaceable without rewriting
the workflow graph.

### Dependencies

- Milestone 6.
- Milestone 9 for end-to-end configuration verification.

### Deliverable

A role-based OpenRouter model configuration layer with replaceable model
implementations and safe failure behavior.

### Checklist

- [ ] Define role-based model configuration.
- [ ] Support question-analysis model selection.
- [ ] Support SQL-generation model selection.
- [ ] Support SQL-correction model selection.
- [ ] Support answer-generation model selection.
- [ ] Support embedding-model selection.
- [ ] Integrate OpenRouter through backend-only configuration.
- [ ] Ensure model IDs are not hardcoded into workflow policy.
- [ ] Allow multiple logical roles to share one configured model.
- [ ] Verify multiple compatible model identifiers can be configured.
- [ ] Add model timeout handling.
- [ ] Add model unavailable and malformed-output handling.
- [ ] Record model role and identifier in telemetry.
- [ ] Add tests using fake model implementations.
- [ ] Test the workflow with at least two configured model options.
- [ ] Document model replacement and configuration procedures.

### Exit Criteria

- [ ] Models can be changed through configuration without rewriting orchestration.
- [ ] API keys remain backend-only.
- [ ] Model failures produce safe, actionable errors.

---

## Milestone 12 - Observability, Testing, and Evaluation

### Objective

Measure correctness, safety, reliability, and latency across the complete
application.

### Dependencies

- Milestones 1-11.

### Deliverable

Automated regression coverage, structured telemetry, and a repeatable benchmark
report for the MVP.

### Checklist

- [ ] Add structured FastAPI logging.
- [ ] Record query IDs and final statuses.
- [ ] Record analysis, embedding, retrieval, generation, validation, correction, execution, and answer timings.
- [ ] Record validation results, failure categories, and retry counts.
- [ ] Record selected source schemas and tables without unnecessary sensitive values.
- [ ] Record row counts and truncation state.
- [ ] Avoid logging credentials and unnecessary customer data.
- [ ] Add unit tests for request validation.
- [ ] Add unit tests for structured model-output parsing.
- [ ] Add unit tests for ambiguity and state policy.
- [ ] Add unit tests for schema document construction.
- [ ] Add unit tests for retrieval merging, ranking, and bounds.
- [ ] Add unit tests for SQL parsing, statement policy, identifier checks, and limits.
- [ ] Add unit tests for exact-SQL and version binding.
- [ ] Add unit tests for result normalization and chart-shape selection.
- [ ] Add security tests for write statements and DDL.
- [ ] Add security tests for multi-statement and obfuscated SQL.
- [ ] Add security tests for hallucinated tables and columns.
- [ ] Add security tests for edited unsafe SQL.
- [ ] Add security tests for Auto Mode bypass attempts.
- [ ] Add security tests for prompt-injection text in database values.
- [ ] Add integration tests for source introspection and fingerprinting.
- [ ] Add integration tests for schema documents and index writes.
- [ ] Add integration tests for vector and metadata retrieval.
- [ ] Add integration tests for source execution, timeouts, and result limits.
- [ ] Add integration tests proving source/index connection separation.
- [ ] Add API tests for the complete query lifecycle.
- [ ] Add frontend tests for the primary user journeys.
- [ ] Add an end-to-end test from question through retrieval, validation, approval, source execution, table, and answer.
- [ ] Add an end-to-end test proving edited SQL is revalidated before execution.
- [ ] Create an evaluation dataset of approximately 50-100 questions.
- [ ] Include lookup, filtering, aggregation, sorting, joins, date/time, nested, and multi-table cases.
- [ ] Include ambiguous, impossible, unsafe, and adversarial questions.
- [ ] Define expected concepts, relationships, filters, grouping, ordering, and result properties.
- [ ] Implement repeatable evaluation runners.
- [ ] Report SQL validity and safety.
- [ ] Report schema retrieval recall and precision.
- [ ] Report relationship accuracy.
- [ ] Report semantic correctness and result correctness.
- [ ] Report clarification accuracy and answer faithfulness.
- [ ] Report latency by pipeline stage.
- [ ] Record failure analysis and known limitations.

### Exit Criteria

- [ ] Automated tests cover the major product, safety, and workflow risks.
- [ ] Evaluation produces repeatable quality metrics.
- [ ] Observability is useful without exposing credentials or unnecessary sensitive data.

---

## Milestone 13 - Portfolio Polish and Release

### Objective

Make the project reproducible, understandable, demonstrable, and ready for
portfolio or MVP release.

### Dependencies

- Milestone 12.

### Deliverable

A documented, reproducible, security-conscious project with a clear demo path
and final MVP evidence.

### Checklist

- [ ] Finalize Docker Compose startup and service dependencies.
- [ ] Configure persistent local index storage.
- [ ] Verify clean-environment startup from documented instructions.
- [ ] Verify `.env.example` contains placeholders only.
- [ ] Scan the repository for accidentally committed secrets.
- [ ] Write architecture documentation.
- [ ] Write security and threat-boundary documentation.
- [ ] Write schema retrieval documentation.
- [ ] Write evaluation documentation.
- [ ] Document source and index database responsibilities.
- [ ] Document controlled agent boundaries.
- [ ] Document SQL validation and execution gates.
- [ ] Document Review Mode and Auto Mode.
- [ ] Document schema indexing and refresh procedures.
- [ ] Document testing and evaluation commands.
- [ ] Create or update architecture diagrams.
- [ ] Add a demo walkthrough.
- [ ] Add representative safe example queries and responses where appropriate.
- [ ] Review README setup instructions from a clean environment.
- [ ] Confirm no fixed business schema is required.
- [ ] Confirm test fixtures are isolated from production schema behavior.
- [ ] Confirm deferred enhancements remain out of MVP scope.
- [ ] Record final evaluation results and known limitations.

### Exit Criteria

- [ ] A new developer can run the system using documented steps.
- [ ] The project clearly demonstrates safe, schema-aware natural-language-to-SQL behavior.
- [ ] The final demo covers Review Mode, SQL editing, revalidation, execution, results, and grounded answers.

---

## Final MVP Gate

These checks must be complete before declaring the MVP finished.

- [ ] Dynamic source database integration works.
- [ ] The same source database is used for introspection and read-only execution.
- [ ] The separate local pgvector index works.
- [ ] Hybrid retrieval works.
- [ ] Relationship expansion is bounded.
- [ ] Controlled agent boundaries are enforced.
- [ ] LCEL workflow is complete.
- [ ] Ambiguous questions request clarification instead of guessing.
- [ ] SQL validation and read-only execution are enforced.
- [ ] Unsafe, multi-statement, hallucinated, and edited unsafe SQL are rejected.
- [ ] Query timeouts, row limits, and result-size limits are enforced.
- [ ] Correction is limited to two attempts.
- [ ] Review Mode is the default.
- [ ] Auto Mode validates before execution.
- [ ] Edited SQL is revalidated by the backend.
- [ ] Results and grounded answers are displayed.
- [ ] Suitable results can be visualized.
- [ ] FastAPI endpoint contracts are tested.
- [ ] React user journeys are tested.
- [ ] Model roles are configuration-driven.
- [ ] Structured observability is implemented without leaking sensitive data.
- [ ] Evaluation dataset and quality reports exist.
- [ ] Docker Compose and local setup are reproducible.
- [ ] Architecture, security, retrieval, evaluation, and README documentation are complete.

## Deferred Enhancements

- [ ] Explicit semantic metric layer.
- [ ] Query plans and cost explanations.
- [ ] LangSmith tracing and evaluation integration.
- [ ] Model routing based on measured performance.
- [ ] Published embedding versus keyword versus hybrid retrieval benchmark.
- [ ] User feedback loops.
- [ ] Advanced authorization and multi-user tenancy.
- [ ] Support for additional database engines.
- [ ] Autonomous agent behavior beyond bounded tools.
- [ ] Production managed PostgreSQL deployment changes.

Deferred work must not weaken deterministic safeguards or read-only database
permissions.
