import type { ExecutionMode } from "../api/types";
import { Panel } from "../design-system";

type Props = {
  question: string;
  mode: ExecutionMode;
  disabled: boolean;
  onQuestion: (value: string) => void;
  onMode: (value: ExecutionMode) => void;
  onSubmit: () => void;
};

export function QueryComposer({ question, mode, disabled, onQuestion, onMode, onSubmit }: Props) {
  return (
    <Panel className="p-[clamp(1.25rem,3vw,2rem)]" aria-labelledby="composer-title">
      <div className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
        Ask the source
      </div>
      <h2
        id="composer-title"
        className="mb-4 font-display text-[clamp(1.5rem,3vw,2.25rem)] font-semibold tracking-[-0.04em]"
      >
        What do you need to know?
      </h2>
      <label className="sr-only" htmlFor="question">
        Natural-language question
      </label>
      <textarea
        id="question"
        value={question}
        onChange={(event) => onQuestion(event.target.value)}
        placeholder="Try: Which regions grew fastest in the last quarter?"
        rows={4}
        maxLength={4_000}
        disabled={disabled}
        className="w-full resize-y rounded-control border border-border bg-surface-muted p-4 leading-[1.55] text-ink outline-none focus:border-accent focus:ring-3 focus:ring-accent/20"
      />
      <div className="mt-5 flex items-end justify-between gap-6 max-[720px]:flex-col max-[720px]:items-stretch">
        <fieldset className="grid w-fit min-w-0 max-w-none flex-none gap-2 border-0 p-0 max-[720px]:w-full">
          <legend className="text-xs font-bold uppercase tracking-[0.1em] text-ink-muted">
            Run mode
          </legend>
          <div className="grid w-fit grid-cols-2 overflow-hidden rounded-control border border-border bg-surface-muted p-1 max-[720px]:w-full">
            <button
              type="button"
              aria-pressed={mode === "REVIEW"}
              className={`h-10 min-w-32 rounded-[0.25rem] px-4 py-2 text-sm font-medium text-ink transition-colors focus-visible:z-1 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-[-3px] max-[720px]:min-w-0 max-[720px]:flex-1 ${mode === "REVIEW" ? "bg-ink text-surface shadow-raised" : "bg-transparent hover:bg-surface"}`}
              onClick={() => onMode("REVIEW")}
              disabled={disabled}
            >
              Review first
            </button>
            <button
              type="button"
              aria-pressed={mode === "AUTO"}
              className={`h-10 min-w-32 rounded-[0.25rem] px-4 py-2 text-sm font-medium text-ink transition-colors focus-visible:z-1 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-[-3px] max-[720px]:min-w-0 max-[720px]:flex-1 ${mode === "AUTO" ? "bg-ink text-surface shadow-raised" : "bg-transparent hover:bg-surface"}`}
              onClick={() => onMode("AUTO")}
              disabled={disabled}
            >
              Auto run
            </button>
          </div>
          <span className="min-h-5 text-xs text-ink-muted max-[720px]:max-w-md">
            {mode === "REVIEW"
              ? "Inspect and approve the exact SQL before execution."
              : "Backend validation still applies before execution."}
          </span>
        </fieldset>
        <button
          className="min-h-11 rounded-control border-2 border-accent bg-accent px-4 py-3 font-bold text-surface transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-3 max-[720px]:w-full"
          type="button"
          onClick={onSubmit}
          disabled={disabled || question.trim().length === 0}
        >
          {disabled ? "Working..." : mode === "REVIEW" ? "Review question" : "Run automatically"}
        </button>
      </div>
    </Panel>
  );
}
