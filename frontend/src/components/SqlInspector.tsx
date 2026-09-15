import { useState } from "react";
import type { QueryResponse } from "../api/types";

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
    <li className={passed ? "check-passed" : "check-blocked"}>
      <span aria-hidden="true">{passed ? "PASS" : "HOLD"}</span>
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
    <section className="inspector panel" aria-labelledby="inspector-title">
      <div className="inspector-header">
        <div>
          <div className="section-kicker">SQL inspector</div>
          <h2 id="inspector-title">A proposal you can inspect</h2>
        </div>
        <span
          className={
            inspector.validation_passed ? "status-badge status-ready" : "status-badge status-failed"
          }
        >
          {inspector.validation_passed ? "Backend validated" : "Blocked"}
        </span>
      </div>
      <p className="interpretation">{inspector.interpretation}</p>
      <div className="sql-toolbar">
        <span>Version {inspector.sql_version.slice(0, 12)}</span>
        <button type="button" onClick={() => navigator.clipboard?.writeText(inspector.sql)}>
          Copy SQL
        </button>
        <button type="button" onClick={() => setEditing((value) => !value)}>
          {editing ? "Close editor" : "Edit SQL"}
        </button>
      </div>
      {editing ? (
        <div className="editor-wrap">
          <label className="sr-only" htmlFor="sql-editor">
            SQL editor
          </label>
          <textarea
            id="sql-editor"
            className="sql-editor"
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            disabled={disabled}
          />
          <p className="editor-warning">
            Edited SQL is untrusted and will be fully revalidated by the backend before execution.
          </p>
          <button
            type="button"
            className="secondary-action"
            onClick={onEdit}
            disabled={disabled || draft.trim().length === 0}
          >
            {disabled ? "Checking..." : "Validate edited SQL"}
          </button>
        </div>
      ) : (
        <pre className="sql-block">
          <code>{inspector.sql}</code>
        </pre>
      )}
      <div className="inspector-grid">
        <div>
          <h3>Used tables</h3>
          <ul className="tag-list">
            {inspector.tables_used.length ? (
              inspector.tables_used.map((table) => <li key={table}>{table}</li>)
            ) : (
              <li>None reported</li>
            )}
          </ul>
        </div>
        <div>
          <h3>Interpretation notes</h3>
          <ul className="plain-list">
            {inspector.assumptions.length ? (
              inspector.assumptions.map((item) => <li key={item}>{item}</li>)
            ) : (
              <li>No additional assumptions.</li>
            )}
          </ul>
        </div>
        <div>
          <h3>Policy checks</h3>
          <ul className="check-list">
            <Check label="Read-only statement" passed={inspector.read_only} />
            <Check label="Single statement" passed={inspector.single_statement} />
            <Check label="Approved source scope" passed={inspector.approved_source} />
            <Check label="Validation passed" passed={inspector.validation_passed} />
          </ul>
        </div>
      </div>
      {validation?.blocking_errors.length || inspector.warnings.length ? (
        <div className="notice-stack">
          {validation?.blocking_errors.map((item) => (
            <div className="notice notice-error" key={item}>
              {item}
            </div>
          ))}
          {inspector.warnings.map((item) => (
            <div className="notice notice-warning" key={item}>
              {item}
            </div>
          ))}
        </div>
      ) : null}
      <div className="inspector-actions">
        <button
          type="button"
          className="secondary-action"
          onClick={onRegenerate}
          disabled={disabled}
        >
          Regenerate proposal
        </button>
        {canApprove ? (
          <button type="button" className="primary-action" onClick={onApprove} disabled={disabled}>
            Approve this SQL
          </button>
        ) : null}
        {canExecute ? (
          <button type="button" className="primary-action" onClick={onExecute} disabled={disabled}>
            {disabled ? "Executing..." : "Execute query"}
          </button>
        ) : null}
      </div>
      {inspector.stale_approval ? (
        <p className="notice notice-warning">
          This approval is stale. The current SQL must be approved again.
        </p>
      ) : null}
    </section>
  );
}
