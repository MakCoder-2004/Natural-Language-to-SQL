# Evaluation Runners

The runner scores sanitized normalized outcomes. It intentionally does not own a
database connection or require live OpenRouter requests.

From the repository root:

```powershell
python evaluation/runners/run_evaluation.py `
  --dataset evaluation/datasets/nl2sql_mvp_v1.json `
  --outcomes path/to/normalized-outcomes.json `
  --output evaluation/reports/nl2sql-mvp.json
```

The outcomes file contains one object per case with fields such as `id`,
`sql_valid`, `unsafe_rejected`, `retrieved_tables`, `relationships`,
`semantic_correct`, `result_correct`, `answer_faithful`, and `latency_ms`.
Generated reports must not contain credentials, raw prompts, or unnecessary rows.
