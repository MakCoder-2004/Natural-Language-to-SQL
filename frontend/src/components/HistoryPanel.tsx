import type { HistoryEntry } from "../state/queryState";
import { Panel } from "../design-system";

function shortStatus(status: string) {
  return status.replaceAll("_", " ");
}

export function HistoryPanel({
  entries,
  onSelect,
}: {
  entries: HistoryEntry[];
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="history panel" aria-labelledby="history-title">
      <Panel className="history-inner">
        <div className="section-kicker">Current session</div>
        <div className="history-heading">
          <h2 id="history-title">Query history</h2>
          <span>{entries.length}</span>
        </div>
        {entries.length === 0 ? (
          <p className="muted">Your recent questions will appear here.</p>
        ) : (
          <ul>
            {entries.map((entry) => (
              <li key={entry.query_id}>
                <button type="button" onClick={() => onSelect(entry.query_id)}>
                  <span className="history-question">{entry.question}</span>
                  <span className="history-meta">
                    {shortStatus(entry.status)} · {entry.execution_mode}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </aside>
  );
}
