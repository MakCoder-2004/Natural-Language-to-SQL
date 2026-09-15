import type { QueryResponse } from "../api/types";

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
      className="chart"
      role="img"
      aria-label={`Chart of ${visualization.y_columns[0]} by ${visualization.x_column}`}
    >
      <div className="chart-bars">
        {result.rows.slice(0, 8).map((row, index) => (
          <div className="chart-column" key={`${String(row[xIndex])}-${index}`}>
            <span
              className="chart-bar"
              style={{ height: `${Math.max(8, (Number(row[yIndex]) / max) * 100)}%` }}
            />
            <span>{String(row[xIndex])}</span>
          </div>
        ))}
      </div>
      <p className="chart-caption">{visualization.reason}</p>
    </div>
  );
}

export function ResultsPanel({ response }: { response: QueryResponse }) {
  const result = response.result;
  if (!result && !response.answer) return null;
  return (
    <section className="results panel" aria-labelledby="results-title">
      <div className="section-kicker">Evidence and answer</div>
      <div className="results-heading">
        <h2 id="results-title">What the source returned</h2>
        {result ? (
          <span className="result-count">
            {result.returned_row_count} of {result.row_count} rows
          </span>
        ) : null}
      </div>
      {response.answer ? (
        <div className="answer-block">
          <h3>Grounded answer</h3>
          <p>{response.answer.answer}</p>
          <p className="evidence">{response.answer.evidence_summary}</p>
          {response.answer.caveats.map((caveat) => (
            <p className="caveat" key={caveat}>
              {caveat}
            </p>
          ))}
        </div>
      ) : null}
      {result?.truncated ? (
        <div className="notice notice-warning">
          The result is truncated to the configured limit. The displayed rows are not the complete
          dataset.
        </div>
      ) : null}
      {result && result.rows.length === 0 ? (
        <div className="empty-result">
          <strong>No rows matched.</strong>
          <span>The query completed, but the source returned no records.</span>
        </div>
      ) : null}
      {result && result.rows.length > 0 ? (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Query result data</caption>
            <thead>
              <tr>
                {result.columns.map((column) => (
                  <th scope="col" key={column}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((value, columnIndex) => (
                    <td key={`${rowIndex}-${columnIndex}`}>{displayValue(value)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {result ? (
        <div className="result-meta">
          <span>{result.result_bytes.toLocaleString()} bytes</span>
          <span>Executed hash {result.executed_sql_hash.slice(0, 12)}</span>
        </div>
      ) : null}
      <Chart response={response} />
    </section>
  );
}
