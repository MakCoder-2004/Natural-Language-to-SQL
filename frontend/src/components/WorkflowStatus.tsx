import type { QueryResponse } from "../api/types";
import { Panel } from "../design-system";

const stages = [
  "ANALYZING",
  "RETRIEVING_SCHEMA",
  "GENERATING_SQL",
  "VALIDATING_SQL",
  "READY_FOR_REVIEW",
  "COMPLETED",
];

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function WorkflowStatus({
  response,
  activeAction,
}: {
  response: QueryResponse | null;
  activeAction: string | null;
}) {
  const current = response?.status ?? (activeAction ? "ANALYZING" : "IDLE");
  const activeIndex = stages.indexOf(current);
  return (
    <Panel className="workflow panel" aria-labelledby="workflow-title">
      <div className="section-kicker">Workflow state</div>
      <div className="workflow-heading">
        <h2 id="workflow-title">{label(current)}</h2>
        <span className={`status-badge status-${current.toLowerCase()}`}>
          {activeAction ? `${label(activeAction)}...` : response ? label(current) : "Waiting"}
        </span>
      </div>
      <ol className="workflow-steps">
        {stages.map((stage, index) => (
          <li
            key={stage}
            className={
              index <= activeIndex && activeIndex >= 0
                ? "is-done"
                : stage === current
                  ? "is-current"
                  : ""
            }
          >
            <span className="step-marker" aria-hidden="true">
              {index + 1}
            </span>
            <span>{label(stage)}</span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
