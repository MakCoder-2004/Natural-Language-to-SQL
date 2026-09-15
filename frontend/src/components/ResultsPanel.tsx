import type { QueryResponse } from "../api/types";
import { Panel } from "../design-system";

function displayValue(value: unknown) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Chart({ response }: { response: QueryResponse }) {
  const result = response.result;
  const visualization = response.visualization;
  if (
    !result ||
    !visualization ||
    visualization.kind === "none" ||
    !visualization.x_column ||
    !visualization.y_columns.length
  )
    return null;
  const xIndex = result.columns.indexOf(visualization.x_column);
  const yIndex = result.columns.indexOf(visualization.y_columns[0]);
  if (xIndex < 0 || yIndex < 0) return null;
  const values = result.rows
    .slice(0, 8)
    .map((row) => Number(row[yIndex]))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  return (
    <div
      className="mt-6 border border-border bg-surface-muted p-4"
      role="img"
      aria-label={`Chart of ${visualization.y_columns[0]} by ${visualization.x_column}`}
    >
      <div className="flex min-h-40 items-end gap-3 border-b border-border px-4 pt-4">
        {result.rows.slice(0, 8).map((row, index) => (
          <div
            className="flex h-36 min-w-8 flex-1 flex-col items-center justify-end gap-2 text-center text-xs text-ink-muted"
            key={`${String(row[xIndex])}-${index}`}
          >
            <span
              className="block min-h-1.5 w-[min(2.5rem,80%)] bg-accent"
              style={{ height: `${Math.max(8, (Number(row[yIndex]) / max) * 100)}%` }}
            />
            <span>{String(row[xIndex])}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 mb-0 text-sm text-ink-muted">{visualization.reason}</p>
    </div>
  );
}

export function ResultsPanel({ response }: { response: QueryResponse }) {
  const result = response.result;
  if (!result && !response.answer) return null;
  return (
    <Panel className="mt-5 p-[clamp(1.25rem,3vw,2rem)]" aria-labelledby="results-title">
      <div className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
        Evidence and answer
      </div>
      <div className="flex items-center justify-between gap-4">
        <h2 id="results-title" className="font-display text-lg font-semibold tracking-[-0.04em]">
          What the source returned
        </h2>
        {result ? (
          <span className="inline-flex w-fit rounded-pill border border-current px-3 py-2 text-xs font-bold uppercase tracking-[0.07em] text-ink-muted">
            {result.returned_row_count} of {result.row_count} rows
          </span>
        ) : null}
      </div>
      {response.answer ? (
        <div className="my-5 border-l-3 border-accent bg-surface-muted p-4">
          <h3 className="mb-3 text-xs font-bold uppercase tracking-[0.1em] text-accent-strong">
            Grounded answer
          </h3>
          <p className="my-2 leading-[1.6]">{response.answer.answer}</p>
          <p className="my-2 text-sm text-ink-muted">{response.answer.evidence_summary}</p>
          {response.answer.caveats.map((caveat) => (
            <p className="my-2 text-sm italic text-ink-muted" key={caveat}>
              {caveat}
            </p>
          ))}
        </div>
      ) : null}
      {result?.truncated ? (
        <div className="border-l-3 border-warning bg-surface-muted px-4 py-3 text-sm leading-[1.45] text-ink-muted">
          The result is truncated to the configured limit. The displayed rows are not the complete
          dataset.
        </div>
      ) : null}
      {result && result.rows.length === 0 ? (
        <div className="my-4 grid gap-2 border border-dashed border-border p-8 text-center text-ink-muted">
          <strong>No rows matched.</strong>
          <span>The query completed, but the source returned no records.</span>
        </div>
      ) : null}
      {result && result.rows.length > 0 ? (
        <div className="mt-4 overflow-x-auto border border-border">
          <table className="w-full min-w-[34rem] border-collapse text-sm">
            <caption className="sr-only">Query result data</caption>
            <thead>
              <tr>
                {result.columns.map((column) => (
                  <th
                    className="border-b border-border bg-surface-muted px-4 py-3 text-left text-xs uppercase tracking-[0.07em]"
                    scope="col"
                    key={column}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((value, columnIndex) => (
                    <td
                      className="border-b border-border px-4 py-3 align-top even:bg-surface-muted/40"
                      key={`${rowIndex}-${columnIndex}`}
                    >
                      {displayValue(value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {result ? (
        <div className="mt-3 flex flex-wrap gap-3 font-code text-xs text-ink-muted">
          <span>{result.result_bytes.toLocaleString()} bytes</span>
          <span>Executed hash {result.executed_sql_hash.slice(0, 12)}</span>
        </div>
      ) : null}
      <Chart response={response} />
    </Panel>
  );
}
