import type { ExecutionMode } from "../api/types";

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
    <section className="composer panel" aria-labelledby="composer-title">
      <div className="section-kicker">Ask the source</div>
      <h2 id="composer-title">What do you need to know?</h2>
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
      />
      <div className="composer-footer">
        <div className="mode-control" aria-label="Execution mode">
          <span className="control-label">Run mode</span>
          <div className="segmented-control">
            <button
              type="button"
              className={mode === "REVIEW" ? "is-selected" : ""}
              onClick={() => onMode("REVIEW")}
              disabled={disabled}
            >
              Review first
            </button>
            <button
              type="button"
              className={mode === "AUTO" ? "is-selected" : ""}
              onClick={() => onMode("AUTO")}
              disabled={disabled}
            >
              Auto run
            </button>
          </div>
          <span className="mode-help">
            {mode === "REVIEW"
              ? "You approve the exact SQL before it runs."
              : "The backend still validates every statement before execution."}
          </span>
        </div>
        <button
          className="primary-action"
          type="button"
          onClick={onSubmit}
          disabled={disabled || question.trim().length === 0}
        >
          {disabled ? "Working..." : mode === "REVIEW" ? "Review question" : "Run automatically"}
        </button>
      </div>
    </section>
  );
}
