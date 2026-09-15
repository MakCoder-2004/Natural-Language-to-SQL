# Final MVP Evidence

## Automated Verification

The Milestone 12 verification recorded:

- Backend test suite: 190 tests passed.
- Frontend Vitest suite: 9 tests passed.
- Evaluation runner tests: 2 tests passed.
- Backend formatting, linting, and strict mypy checks passed.
- Frontend formatting, linting, typechecking, and production build passed.
- Evaluation dataset: 50 cases.

The dataset covers lookups, filtering, aggregation, sorting, joins, date/time,
nested and multi-table queries, ambiguity, impossible requests, unsafe SQL, and
adversarial inputs.

## Evaluation Status

The repository contains a repeatable metrics runner and normalized-outcome
contract. A full model-quality report requires an external source database and
OpenRouter credentials, so no fabricated end-to-end quality score is recorded
here. Reports generated from real runs must be sanitized and must not contain
credentials, prompts, raw business rows, or unnecessary sensitive values.

## Known Limitations

- Evaluation outcomes are supplied through a normalized contract rather than
  collected automatically by the benchmark runner.
- Model quality depends on the configured OpenRouter models and source schema.
- Integration tests use disposable fixtures and do not represent a production
  business schema.
- Workflow state is held in backend process memory for the current MVP.
