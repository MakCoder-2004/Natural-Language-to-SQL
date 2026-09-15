import { useState } from "react";
import type { QueryResponse } from "../api/types";
import { Panel } from "../design-system";

type Props = {
  response: QueryResponse;
  draft: string;
  disabled: boolean;
  onDraft: (value: string) => void;
  onEdit: () => void;
  onApprove: () => void;
  onExecute: () => void;
  onRegenerate: () => void;
};

function Check({ label, passed }: { label: string; passed: boolean }) {
  return (
    <li className="flex items-center gap-2 text-sm text-ink-muted">
      <span className={passed ? "text-success" : "text-danger"} aria-hidden="true">
        {passed ? "PASS" : "HOLD"}
      </span>
      {label}
    </li>
  );
}

export function SqlInspector({
  response,
  draft,
  disabled,
  onDraft,
  onEdit,
  onApprove,
  onExecute,
  onRegenerate,
}: Props) {
  const inspector = response.sql_inspector;
  const validation = response.validation;
  const [editing, setEditing] = useState(false);
  if (!inspector) return null;
  const canApprove =
    inspector.approval_required &&
    inspector.validation_passed &&
    !inspector.approved &&
    !inspector.stale_approval;
  const canExecute =
    inspector.approved || (!inspector.approval_required && inspector.validation_passed);
  return (
    <Panel className="mt-5 p-[clamp(1.25rem,3vw,2rem)]" aria-labelledby="inspector-title">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
            SQL inspector
          </div>
          <h2
            id="inspector-title"
            className="font-display text-lg font-semibold tracking-[-0.04em]"
          >
            A proposal you can inspect
          </h2>
        </div>
        <span
          className={`inline-flex w-fit rounded-pill border border-current px-3 py-2 text-xs font-bold uppercase tracking-[0.07em] ${inspector.validation_passed ? "text-success" : "text-danger"}`}
        >
          {inspector.validation_passed ? "Backend validated" : "Blocked"}
        </span>
      </div>
      <p className="max-w-[46rem] leading-[1.55] text-ink-muted">{inspector.interpretation}</p>
      <div className="mt-5 flex items-center gap-2 font-code text-xs text-ink-muted">
        <span className="mr-auto">Version {inspector.sql_version.slice(0, 12)}</span>
        <button type="button" onClick={() => navigator.clipboard?.writeText(inspector.sql)}>
          Copy SQL
        </button>
        <button type="button" onClick={() => setEditing((value) => !value)}>
          {editing ? "Close editor" : "Edit SQL"}
        </button>
      </div>
      {editing ? (
        <div>
          <label className="sr-only" htmlFor="sql-editor">
            SQL editor
          </label>
          <textarea
            id="sql-editor"
            className="min-h-40 w-full resize-y rounded-control border border-border bg-code-background p-5 font-code text-sm leading-[1.65] text-ink outline-none focus:border-accent focus:ring-3 focus:ring-accent/20"
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            disabled={disabled}
          />
          <p className="text-sm text-warning">
            Edited SQL is untrusted and will be fully revalidated by the backend before execution.
          </p>
          <button
            type="button"
            className="mb-4 min-h-11 rounded-control border-2 border-border-strong bg-transparent px-4 py-3 font-bold text-ink disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-3"
            onClick={onEdit}
            disabled={disabled || draft.trim().length === 0}
          >
            {disabled ? "Checking..." : "Validate edited SQL"}
          </button>
        </div>
      ) : (
        <pre className="my-3 mb-5 min-h-40 overflow-auto rounded-control border border-border bg-code-background p-5 font-code text-sm leading-[1.65] whitespace-pre-wrap">
          <code>{inspector.sql}</code>
        </pre>
      )}
      <div className="grid grid-cols-3 gap-4 max-[720px]:grid-cols-1">
        <div>
          <h3 className="mb-3 text-xs uppercase tracking-[0.1em]">Used tables</h3>
          <ul className="flex flex-wrap gap-2 text-sm text-ink-muted">
            {inspector.tables_used.length ? (
              inspector.tables_used.map((table) => (
                <li className="rounded-control border border-border px-3 py-2" key={table}>
                  {table}
                </li>
              ))
            ) : (
              <li className="rounded-control border border-border px-3 py-2">None reported</li>
            )}
          </ul>
        </div>
        <div>
          <h3 className="mb-3 text-xs uppercase tracking-[0.1em]">Interpretation notes</h3>
          <ul className="list-square pl-4 text-sm leading-[1.5] text-ink-muted">
            {inspector.assumptions.length ? (
              inspector.assumptions.map((item) => <li key={item}>{item}</li>)
            ) : (
              <li>No additional assumptions.</li>
            )}
          </ul>
        </div>
        <div>
          <h3 className="mb-3 text-xs uppercase tracking-[0.1em]">Policy checks</h3>
          <ul className="grid gap-2">
            <Check label="Read-only statement" passed={inspector.read_only} />
            <Check label="Single statement" passed={inspector.single_statement} />
            <Check label="Approved source scope" passed={inspector.approved_source} />
            <Check label="Validation passed" passed={inspector.validation_passed} />
          </ul>
        </div>
      </div>
      {validation?.blocking_errors.length || inspector.warnings.length ? (
        <div className="mt-4 grid gap-2">
          {validation?.blocking_errors.map((item) => (
            <div
              className="border-l-3 border-danger bg-surface-muted px-4 py-3 text-sm leading-[1.45] text-ink-muted"
              key={item}
            >
              {item}
            </div>
          ))}
          {inspector.warnings.map((item) => (
            <div
              className="border-l-3 border-warning bg-surface-muted px-4 py-3 text-sm leading-[1.45] text-ink-muted"
              key={item}
            >
              {item}
            </div>
          ))}
        </div>
      ) : null}
      <div className="mt-5 flex flex-wrap justify-end gap-3">
        <button
          type="button"
          className="min-h-11 rounded-control border-2 border-border-strong bg-transparent px-4 py-3 font-bold text-ink disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-3"
          onClick={onRegenerate}
          disabled={disabled}
        >
          Regenerate proposal
        </button>
        {canApprove ? (
          <button
            type="button"
            className="min-h-11 rounded-control border-2 border-accent bg-accent px-4 py-3 font-bold text-surface disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-3"
            onClick={onApprove}
            disabled={disabled}
          >
            Approve this SQL
          </button>
        ) : null}
        {canExecute ? (
          <button
            type="button"
            className="min-h-11 rounded-control border-2 border-accent bg-accent px-4 py-3 font-bold text-surface disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-3"
            onClick={onExecute}
            disabled={disabled}
          >
            {disabled ? "Executing..." : "Execute query"}
          </button>
        ) : null}
      </div>
      {inspector.stale_approval ? (
        <p className="mt-4 border-l-3 border-warning bg-surface-muted px-4 py-3 text-sm leading-[1.45] text-ink-muted">
          This approval is stale. The current SQL must be approved again.
        </p>
      ) : null}
    </Panel>
  );
}
