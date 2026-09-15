# Evaluation

Milestone 12 evaluates the natural-language-to-SQL workflow against the versioned
fixture-linked dataset at `evaluation/datasets/nl2sql_mvp_v1.json`.

## Dataset

The dataset contains 50 cases covering lookup, filtering, aggregation, sorting,
joins, date/time, multi-table, nested, ambiguous, impossible, unsafe, and
adversarial requests. Expected tables, concepts, and relationships are labels for
scoring; business rows remain in disposable test fixtures.

## Outcomes And Runner

The runner consumes sanitized normalized outcomes rather than connecting to a
database itself. This keeps evaluation deterministic and prevents evaluation code
from selecting production connections. Deterministic fake-model outcomes are the
recommended regression mode. Live OpenRouter evaluation is optional and must use
backend-managed configuration.

The runner reports SQL validity and safety, retrieval recall and precision,
relationship accuracy, semantic and result correctness, clarification accuracy,
answer faithfulness, latency, missing outcomes, and failure categories.

See `evaluation/runners/README.md` for the command and normalized outcome fields.

## Privacy

Do not include API keys, database URLs, raw prompts, full SQL, or unnecessary
business rows in reports. Prefer query IDs, SQL hashes, structural labels, counts,
and safe failure categories.
