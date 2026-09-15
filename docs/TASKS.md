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

- [x] Create the `backend/` directory and application package structure.
- [x] Create the `frontend/` directory and application package structure.
- [x] Create `schema_index/metadata/` and `schema_index/scripts/` directories.
- [x] Create `evaluation/datasets/`, `evaluation/runners/`, and `evaluation/reports/` directories.
- [x] Create `tests/fixtures/` and keep fixture database setup isolated from production code.
- [x] Create documentation directories for architecture, security, retrieval, and evaluation.
- [x] Configure the backend language version and dependency management.
- [x] Configure the frontend runtime, package manager, and dependency management.
- [x] Add formatting, linting, type-checking, and test commands for the backend.
- [x] Add formatting, linting, type-checking, and test commands for the frontend.
- [x] Add `.env.example` containing placeholders only.
- [x] Define `SOURCE_DATABASE_URL` configuration.
- [x] Define `INDEX_DATABASE_URL` configuration.
- [x] Define OpenRouter API key and model-role configuration.
- [x] Define query timeout, returned-row, result-byte, and correction-retry limits.
- [x] Define source schema scope configuration.
- [x] Add Docker Compose for the backend, frontend, and local pgvector database.
- [x] Do not add a source business database container, business migrations, or business seed data.
- [x] Add initial backend startup configuration validation.
- [x] Add an initial `/api/health` endpoint or health placeholder.
- [x] Document the external source database and local index database responsibilities.
- [x] Document local startup commands.

### Exit Criteria

- [x] Local services start successfully with documented commands.
- [x] Missing required configuration produces safe, actionable errors.
- [x] No application code assumes tables such as `customers`, `orders`, or `products`.
- [x] No secrets are committed.

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

- [x] Implement a dedicated source database connection service.
- [x] Implement a separate index database connection service.
- [x] Make source and index connection dependencies explicit and typed.
- [x] Verify source and index connections cannot be accidentally swapped.
- [x] Integrate LangChain's PostgreSQL SQL abstraction where appropriate.
- [x] Configure source connection pooling and cleanup.
- [x] Configure connection and query timeouts.
- [x] Implement configurable source schema scope filtering.
- [x] Exclude unintended PostgreSQL system schemas from the source scope.
- [x] Introspect source schemas and namespaces.
- [x] Introspect tables and views in the approved source scope.
- [x] Introspect columns, data types, nullability, defaults, and comments.
- [x] Introspect primary keys and unique constraints.
- [x] Introspect foreign keys and relationship metadata.
- [x] Introspect relevant indexes and ordering information.
- [x] Generate a stable source schema fingerprint.
- [x] Verify the source connection is used for both introspection and query execution.
- [x] Document the required read-only source database role.
- [x] Verify that the source role cannot write or alter schema objects.
- [x] Add connection failure and permission failure handling.
- [x] Add integration tests against a disposable or dedicated PostgreSQL test database.

### Exit Criteria

- [x] The backend can inspect an arbitrary supported source PostgreSQL database.
- [x] Introspection returns enough metadata for document generation and SQL validation.
- [x] The application does not modify, migrate, or seed the source database.
- [x] Source and index connections remain isolated.

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

- [x] Define the versioned semantic metadata format.
- [x] Support descriptions for discovered schemas, tables, columns, and relationships.
- [x] Ensure semantic metadata can describe arbitrary source identifiers.
- [x] Define metadata behavior for missing or stale semantic descriptions.
- [x] Build schema documents from technical metadata.
- [x] Include qualified identifiers, types, constraints, relationships, and descriptions.
- [x] Include source fingerprint and document version in every indexed document.
- [x] Define document categories for tables, columns, relationships, and semantic concepts.
- [x] Enable the pgvector extension in the local index database.
- [x] Define local index tables for documents, embeddings, metadata, and index runs.
- [x] Keep local index schema initialization separate from source business schema management.
- [x] Implement embedding generation through the configured embedding model.
- [x] Implement idempotent document upsert behavior.
- [x] Store source fingerprints and indexing timestamps.
- [x] Store embedding model identifiers and document versions.
- [x] Implement a repeatable indexing command or script.
- [x] Implement index refresh behavior for source schema changes.
- [x] Implement index readiness and freshness checks.
- [x] Report indexing failures without exposing secrets.
- [x] Add tests for document generation and semantic metadata merging.
- [x] Add tests for repeat indexing and stale-document replacement.
- [x] Add integration tests for pgvector writes and reads.

### Exit Criteria

- [x] A real source schema can be indexed without hardcoded business tables.
- [x] Re-running indexing does not create uncontrolled duplicates.
- [x] The local index contains searchable documents and embeddings.
- [x] Index readiness and source freshness are observable.

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

- [x] Implement semantic vector retrieval from the local index.
- [x] Implement keyword or metadata retrieval from the local index.
- [x] Combine retrieval signals using explicit ranking logic.
- [x] Make retrieval limits configurable.
- [x] Implement table and column candidate ranking.
- [x] Implement bounded foreign-key relationship expansion.
- [x] Include nearby tables and columns only when justified by retrieved candidates.
- [x] Include semantic descriptions in ranking and final context.
- [x] Remove duplicate documents and redundant metadata.
- [x] Produce a compact structured retrieval result.
- [x] Include source fingerprint and retrieval diagnostics in the result.
- [x] Handle an empty or unavailable index safely.
- [x] Return a clear index-readiness error when runtime retrieval is impossible.
- [x] Add retrieval latency measurements.
- [x] Add tests for keyword retrieval.
- [x] Add tests for vector retrieval.
- [x] Add tests for signal merging and ranking.
- [x] Add tests for relationship expansion bounds.
- [x] Add tests proving retrieval does not return uncontrolled full-schema context.

### Exit Criteria

- [x] Relevant source schema context is returned for arbitrary supported questions.
- [x] Both vector and non-vector retrieval signals are used.
- [x] Relationship expansion is bounded and deterministic.
- [x] SQL generation receives compact relevant context rather than the full database.

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

- [x] Define request, response, and internal domain models.
- [x] Define the query ID and query lifecycle identifiers.
- [x] Implement natural-language question input handling.
- [x] Implement initial SQL generation using LangChain.
- [x] Define structured SQL proposal output.
- [x] Include interpretation, tables, assumptions, warnings, and SQL in proposals.
- [x] Connect SQL generation to retrieved schema context.
- [x] Define a validation service interface before implementing pipeline execution.
- [x] Route generated SQL through the validation service.
- [x] Route execution only through the source database service.
- [x] Normalize returned columns and rows.
- [x] Represent empty results distinctly from failures.
- [x] Represent truncation and result limits in responses.
- [x] Generate a grounded answer from executed results.
- [x] Generate a basic visualization selection result.
- [x] Add safe handling for model, validation, index, and database failures.
- [x] Add a backend integration test for a successful clear question.
- [x] Add an integration test for a valid query returning zero rows.
- [x] Verify there is no execution path that bypasses validation.

### Exit Criteria

- [x] A clear question can produce a validated read-only query and normalized result.
- [x] The answer is based on executed data, not generated claims.
- [x] Empty and truncated results are represented correctly.
- [x] The pipeline uses the external source database and local schema index correctly.

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

- [x] Define the complete query state model.
- [x] Define valid query states and allowed transitions.
- [x] Implement structured question analysis.
- [x] Detect ambiguity before SQL generation.
- [x] Define clarification choices and clarification state.
- [x] Prevent SQL generation while clarification is outstanding.
- [x] Compose analysis, retrieval, generation, validation, execution, and answer stages with LCEL.
- [x] Implement bounded `get_relevant_schema`.
- [x] Implement bounded `generate_sql`.
- [x] Implement bounded `execute_readonly_sql`.
- [x] Ensure `get_relevant_schema` reads only the local index.
- [x] Ensure `execute_readonly_sql` targets only the source database.
- [x] Ensure tools receive no credentials or connection details.
- [x] Ensure the agent cannot mutate workflow state or bypass gates.
- [x] Limit the agent to approved application tools.
- [x] Add structured model-output parsing and missing-field validation.
- [x] Implement regeneration behavior through the workflow state.
- [x] Implement graceful handling for impossible and unsupported questions.
- [x] Add tests for valid questions and state transitions.
- [x] Add tests for ambiguous questions.
- [x] Add tests for impossible questions.
- [x] Add tests proving the agent cannot access credentials or arbitrary connections.

### Exit Criteria

- [x] The core workflow is composable, state-driven, and inspectable.
- [x] Ambiguous questions stop before SQL generation.
- [x] The controlled agent cannot directly access databases or secrets.
- [x] The workflow has no hidden execution route outside the application gates.

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

- [x] Allow one read-only `SELECT` statement by default.
- [x] Add carefully validated `WITH ... SELECT` support if enabled.
- [x] Reject `INSERT`, `UPDATE`, `DELETE`, and `MERGE`.
- [x] Reject DDL statements.
- [x] Reject transaction control statements.
- [x] Reject `GRANT`, `REVOKE`, and other privilege operations.
- [x] Reject multi-statement SQL.
- [x] Detect hidden statements in comments and formatting.
- [x] Validate referenced schemas against the approved source scope.
- [x] Validate referenced tables against introspected source metadata.
- [x] Validate referenced columns against introspected source metadata.
- [x] Reject references to the local index database.
- [x] Define and enforce suspicious or unsupported construct policy.
- [x] Enforce statement timeouts.
- [x] Enforce returned-row limits.
- [x] Enforce result byte limits.
- [x] Represent truncation and pagination in results.
- [x] Implement a maximum of two correction attempts.
- [x] Pass validation errors to correction without exposing unnecessary sensitive data.
- [x] Revalidate the exact SQL at every execution endpoint.
- [x] Bind approval to the SQL version or hash.
- [x] Verify the PostgreSQL runtime role is read-only.
- [x] Add unit tests for every statement policy category.
- [x] Add security tests for multi-statement and comment-obfuscated SQL.
- [x] Add security tests for hallucinated tables and columns.
- [x] Add security tests for index database references.
- [x] Add tests for timeouts, row limits, bytes limits, and correction exhaustion.

### Exit Criteria

- [x] Unsafe SQL is rejected deterministically.
- [x] Correction cannot loop indefinitely.
- [x] Edited SQL cannot bypass backend validation.
- [x] Database permissions provide an independent safety boundary.

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

- [x] Implement Review Mode as the default execution mode.
- [x] Add explicit Auto Mode support.
- [x] Require approval before Review Mode execution.
- [x] Prevent approval when validation fails.
- [x] Store the exact proposed SQL and current SQL version.
- [x] Support SQL editing in Review Mode.
- [x] Revalidate edited SQL on the backend.
- [x] Invalidate stale approvals after SQL edits.
- [x] Display interpretation, assumptions, tables, validation, and warnings.
- [x] Display read-only status.
- [x] Display approved-source status.
- [x] Display multi-statement status.
- [x] Display resource-limit status.
- [x] Implement safe regeneration.
- [x] Preserve the original natural-language question through clarification and review.
- [x] Add tests for approval and execution gates.
- [x] Add tests for edited valid SQL.
- [x] Add tests for edited unsafe SQL.
- [x] Add tests for stale approvals.
- [x] Add tests proving Auto Mode still validates SQL.

### Exit Criteria

- [x] Review Mode cannot execute without explicit approval.
- [x] Auto Mode performs deterministic validation before execution.
- [x] The executed SQL is exactly the SQL that was validated and approved.
- [x] Regeneration does not silently execute a new proposal.

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

- [x] Create FastAPI application entrypoint and dependency wiring.
- [x] Create request and response schemas for all public endpoints.
- [x] Implement `POST /api/query`.
- [x] Implement `POST /api/query/{query_id}/clarify`.
- [x] Implement `POST /api/query/{query_id}/edit` for untrusted SQL edits.
- [x] Implement `POST /api/query/{query_id}/approve`.
- [x] Implement `POST /api/query/{query_id}/execute`.
- [x] Implement `POST /api/query/{query_id}/regenerate`.
- [x] Implement `GET /api/query/{query_id}`.
- [x] Implement `GET /api/health`.
- [x] Make execution mode explicit in API requests and responses.
- [x] Return query IDs for query lifecycle operations.
- [x] Return clarification data without generating SQL prematurely.
- [x] Return SQL Inspector data in structured response fields.
- [x] Return normalized result columns, rows, limits, and truncation state.
- [x] Return grounded answer and optional visualization data separately from SQL text.
- [x] Add request validation for malformed or incomplete payloads.
- [x] Map domain errors to safe HTTP responses.
- [x] Map ambiguous, unsafe, correction-exhausted, database, and index failures distinctly.
- [x] Ensure raw backend stack traces are not returned to normal users.
- [x] Ensure routes do not contain the complete LLM or SQL workflow.
- [x] Add dependency injection for query, indexing, database, model, and telemetry services.
- [x] Add CORS configuration for the local frontend.
- [x] Add API documentation for request and response contracts.
- [x] Add API tests for clear, ambiguous, impossible, unsafe, and failed queries.
- [x] Add API tests for approval, execution, regeneration, lookup, and health.
- [x] Add API tests proving every execution request revalidates exact SQL.
- [x] Add API tests proving frontend-provided validation cannot authorize execution.

### Exit Criteria

- [x] Every required API endpoint exists and has a tested contract.
- [x] FastAPI routes delegate to backend services instead of containing orchestration logic.
- [x] API responses are safe, structured, and sufficient for the frontend.
- [x] No database credentials or connection details appear in API responses.

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

- [x] Create the React application shell and route structure.
- [x] Create a typed or validated FastAPI API client.
- [x] Implement natural-language query input.
- [x] Preserve the question while clarification is requested.
- [x] Implement loading states for every asynchronous query action.
- [x] Implement safe user-facing error states.
- [x] Implement execution mode selection with Review Mode as the default.
- [x] Implement clarification panel or modal.
- [x] Disable execution actions while clarification is outstanding.
- [x] Implement SQL Inspector component.
- [x] Display exact SQL proposal.
- [x] Display interpretation, assumptions, tables, validation, and warnings.
- [x] Display read-only, source-scope, multi-statement, and resource-limit status.
- [x] Implement SQL editor for Review Mode.
- [x] Clearly state that edited SQL is revalidated by the backend.
- [x] Implement approve and execute actions.
- [x] Implement regeneration action.
- [x] Implement results table with normalized columns and rows.
- [x] Implement empty-result state.
- [x] Implement truncation and pagination indication.
- [x] Render returned values safely as data.
- [x] Implement grounded answer panel separate from SQL proposal text.
- [x] Implement conditional chart components for suitable result shapes.
- [x] Implement current-session query history.
- [x] Show query ID, short question, status, execution mode, and timestamp when available.
- [x] Prevent frontend-only validation indicators from authorizing execution.
- [x] Ensure the frontend never receives or stores database credentials.
- [x] Ensure the frontend communicates only with FastAPI.
- [x] Make the main workflow usable on desktop and mobile layouts.
- [x] Add component tests for query input, loading, errors, clarification, and SQL Inspector.
- [x] Add component tests for editing, approval, Auto Mode, and regeneration.
- [x] Add component tests for table, empty, truncated, and chart results.
- [x] Add component tests for current-session history.
- [x] Add a frontend integration test for the primary Review Mode journey.

### Exit Criteria

- [x] A user can complete the full query, clarification, review, approval, execution, and answer flow.
- [x] Auto Mode is visible and understandable without weakening backend safeguards.
- [x] The UI handles loading, empty, truncated, validation, and failure states.
- [x] The application works on desktop and mobile layouts.

### Design Polish Checklist

- [x] Remove the detached upper navigation header and preserve system context in-flow.
- [x] Reduce hero typography and compact supporting copy.
- [x] Redesign current-session history as one semantic surface with query metadata.
- [x] Align Review Mode and Auto Mode controls with accessible pressed states and compact sizing.
- [x] Keep workflow progress on one horizontal sequence with mobile overflow.
- [x] Keep safety explanations in the query workflow and SQL inspector rather than a separate rail.
- [x] Expand the Query History column for readable session context.
- [x] Remove the obsolete footer from the production workspace.
- [x] Remove the public component-library route and document the design system in Markdown.
- [x] Use Tailwind utilities and theme tokens for production frontend styling.
- [x] Verify formatting, linting, typechecking, tests, production build, and browser smoke behavior.

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
