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

const stageLabels = ["Analysis", "Schema", "SQL draft", "Safety check", "Review", "Complete"];

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
    <Panel
      className="mt-5 overflow-hidden p-[clamp(1.25rem,3vw,2rem)]"
      aria-labelledby="workflow-title"
    >
      <div className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
        Workflow state
      </div>
      <div className="flex items-center justify-between gap-4">
        <h2 id="workflow-title" className="font-display text-lg font-semibold tracking-[-0.04em]">
          {current === "IDLE" ? "Ready for a question" : label(current)}
        </h2>
        <span className="inline-flex w-fit rounded-pill border border-current px-3 py-2 text-xs font-bold uppercase tracking-[0.07em] text-ink-muted">
          {activeAction ? `${label(activeAction)}...` : response ? label(current) : "Ready"}
        </span>
      </div>
      <div className="mt-5 overflow-x-auto pb-2">
        <ol className="grid min-w-[44rem] grid-cols-6 list-none gap-0 p-0">
          {stages.map((stage, index) => (
            <li
              key={stage}
              aria-current={stage === current ? "step" : undefined}
              className={`relative flex min-w-0 flex-col items-center gap-2 text-center text-xs uppercase text-ink-muted ${index <= activeIndex && activeIndex >= 0 ? "font-bold text-ink" : ""} ${stage === current ? "text-accent" : ""}`}
            >
              {index < stages.length - 1 ? (
                <span
                  className={`absolute left-1/2 right-[-50%] top-3 h-px ${index < activeIndex ? "bg-success" : "bg-border"}`}
                  aria-hidden="true"
                />
              ) : null}
              <span
                className={`relative z-1 grid size-6 place-items-center rounded-full border text-xs ${index < activeIndex ? "border-success bg-success text-surface" : stage === current ? "border-accent bg-accent text-surface" : "border-border-strong bg-surface text-ink-muted"}`}
                aria-hidden="true"
              >
                {index + 1}
              </span>
              <span className="whitespace-nowrap">{stageLabels[index]}</span>
            </li>
          ))}
        </ol>
      </div>
      <p className="sr-only">Current workflow stage: {label(current)}</p>
    </Panel>
  );
}
