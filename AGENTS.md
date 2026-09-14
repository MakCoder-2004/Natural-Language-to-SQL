# Agent Instructions

## Repository State

- The repository currently contains `docs/PLAN.md` and `docs/TASKS.md`; application code has not been scaffolded yet.
- No root README, package manifest, Python manifest, build configuration, test configuration, CI workflow, or `opencode.json` is currently present.
- Do not invent development commands. Once manifests and scripts exist, inspect them and use their commands as the source of truth.
- Git metadata is not currently present. The milestone workflow below is mandatory once Git is available; do not start implementation if the required branch and commit workflow cannot be followed.

## Source Of Truth

- Treat `docs/PLAN.md` as the complete and authoritative requirements and implementation specification.
- Treat `docs/TASKS.md` as the implementation tracker. Update its checkboxes only after the corresponding work and verification are complete.

## Architecture Invariants

- Connect to an existing external PostgreSQL source database; do not create, migrate, seed, or modify its business schema.
- Use that same source database for schema introspection and read-only query execution.
- Use a separate local PostgreSQL + pgvector database for schema documents, metadata, embeddings, and retrieval.
- Never target the local index database with generated business SQL.
- Do not hardcode example business tables such as `customers`, `orders`, or `products`; representative schemas belong only in isolated test fixtures.
- Keep the controlled agent limited to `get_relevant_schema`, `generate_sql`, and `execute_readonly_sql`.
- Keep workflow state, approval gates, retry limits, resource limits, database connections, and SQL policy in deterministic application code.
- The LLM proposes SQL; deterministic backend validation authorizes it; PostgreSQL read-only permissions provide the final boundary.
- Revalidate the exact SQL supplied by the frontend immediately before every execution, including edited SQL.
- Review Mode is the default and requires approval. Auto Mode must still pass every backend validation and limit check.
- Keep database credentials, connection URLs, and OpenRouter keys on the backend; never send them to React or model prompts.
- Do not embed business rows for primary schema retrieval.
- MVP observability uses structured application logging; do not add a proxy or require LangSmith unless the plan changes.

## Milestone Workflow

- Implement every new milestone on a new dedicated branch; never implement a milestone directly on the default branch.
- Use a branch name such as `milestone/09-fastapi-api` or `milestone/10-react-ui`.
- If Git is unavailable, stop before implementation and ask for the repository to be initialized so the branch and commit requirements can be honored.
- Follow milestone dependencies and the order in `docs/TASKS.md`; do not silently skip prerequisite work.
- Complete each milestone phase or task step fully, including its focused verification, before marking it complete.
- After each completed phase or task step, update the corresponding `docs/TASKS.md` checklist entries and commit the implementation, tests, documentation, and checklist update together.
- Never mark a task complete based only on intent or partial implementation.
- Keep commits scoped to the completed phase and use a message that names the milestone and phase.
- Do not combine unrelated milestone work in one branch or commit.
- At milestone completion, run every applicable check defined by the current manifests and scripts, then record the result before handing off or merging the branch.
- Change `docs/PLAN.md` only when requirements or architecture change; record normal implementation progress in `docs/TASKS.md`.

## Directory Boundaries

- `backend/` owns FastAPI transport, LCEL orchestration, models, retrieval, validation, source access, index access, and backend services.
- `frontend/` owns React components and presentation; it communicates only with FastAPI.
- `schema_index/` owns semantic metadata, indexing scripts, documents, embeddings, and local index operations; it must not become a source business schema.
- `tests/fixtures/` may contain representative schemas and data for tests only.
- `evaluation/` owns benchmark cases, runners, reports, and failure analysis.
- `docs/` owns architecture, security, retrieval, and evaluation documentation.

## Verification Rules

- Prefer the executable configuration and scripts over prose when they disagree.
- Before adding a command to documentation or instructions, verify it exists in a manifest, script, Makefile, task runner, or CI workflow.
- For backend changes, use the configured formatter, linter, type checker, focused tests, and full test suite when available.
- For frontend changes, use the configured formatter, linter, type checker, focused tests, and production build when available.
- For database changes, verify source/index connection separation and use isolated test fixtures rather than changing the external source database.
- For security-sensitive changes, test unsafe SQL, multi-statement SQL, hallucinated identifiers, edited SQL, Auto Mode, and prompt-injection text in database values.
- For API changes, verify that frontend-provided validation or approval fields cannot authorize execution without backend checks.
