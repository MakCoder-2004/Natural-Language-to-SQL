import type { HistoryEntry } from "../state/queryState";

function shortStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatTimestamp(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function statusTone(status: string) {
  if (status === "COMPLETED") return "is-complete";
  if (status === "FAILED" || status === "CORRECTION_EXHAUSTED") return "is-danger";
  if (status === "CLARIFICATION_REQUIRED") return "is-warning";
  return "is-pending";
}

export function HistoryPanel({
  entries,
  onSelect,
  onClose,
}: {
  entries: HistoryEntry[];
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <aside
      className="sticky top-4 self-start overflow-hidden rounded-panel border border-border bg-surface p-4 shadow-panel max-[720px]:static max-[720px]:order-2"
      aria-labelledby="history-title"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="mb-2 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
            Current session
          </div>
          <h2 id="history-title" className="font-display text-lg font-semibold tracking-[-0.04em]">
            Query history
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="grid size-6 place-items-center rounded-full bg-surface-muted font-code text-xs text-ink"
            aria-label={`${entries.length} queries`}
          >
            {entries.length}
          </span>
          <button
            type="button"
            className="rounded-control border border-border bg-transparent px-2 py-1 text-xs font-bold uppercase tracking-[0.06em] text-ink-muted transition-colors hover:border-accent hover:text-accent-strong focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-2"
            onClick={onClose}
            aria-label="Hide query history"
          >
            Close
          </button>
        </div>
      </header>
      {entries.length === 0 ? (
        <div className="relative mt-6 grid gap-2 border-t border-border py-5 pl-5 text-sm leading-[1.5] text-ink-muted">
          <span
            className="absolute bottom-3 left-1 top-5 w-px bg-success before:absolute before:-left-[0.2rem] before:top-0 before:size-[0.45rem] before:rounded-full before:bg-success before:content-['']"
            aria-hidden="true"
          />
          <strong className="text-ink">No expeditions yet.</strong>
          <p className="m-0">
            Questions you run during this session will be logged here for quick return.
          </p>
        </div>
      ) : (
        <ol className="mt-4 grid list-none gap-0 p-0">
          {entries.map((entry, index) => (
            <li
              key={entry.query_id}
              className={`relative border-t border-border before:absolute before:left-0 before:top-[1.15rem] before:size-[0.4rem] before:rounded-full before:bg-border-strong before:content-[''] ${
                statusTone(entry.status) === "is-complete"
                  ? "before:bg-success"
                  : statusTone(entry.status) === "is-warning"
                    ? "before:bg-warning"
                    : statusTone(entry.status) === "is-danger"
                      ? "before:bg-danger"
                      : ""
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(entry.query_id)}
                aria-label={`Open query ${index + 1}: ${entry.question}`}
                className="block w-full border-0 border-l-2 border-transparent bg-transparent py-4 pl-4 text-left text-ink hover:border-accent hover:bg-surface-muted focus-visible:border-accent focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-[-3px]"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-code text-xs text-ink-muted">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="text-xs font-bold uppercase tracking-[0.06em] text-success">
                    {shortStatus(entry.status)}
                  </span>
                </span>
                <span className="mt-2 block truncate text-sm">{entry.question}</span>
                <span className="mt-2 block truncate text-xs uppercase text-ink-muted">
                  {entry.execution_mode} · {formatTimestamp(entry.created_at)}
                </span>
                <span className="mt-1 block truncate font-code text-xs text-ink-muted">
                  {entry.query_id}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
