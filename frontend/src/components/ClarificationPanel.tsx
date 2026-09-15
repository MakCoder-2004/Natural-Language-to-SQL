import type { QueryResponse } from "../api/types";
import { Panel } from "../design-system";

type Props = {
  response: QueryResponse;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ClarificationPanel({ response, value, disabled, onChange, onSubmit }: Props) {
  const clarification = response.clarification;
  if (response.status !== "CLARIFICATION_REQUIRED" || !clarification) return null;
  return (
    <Panel
      className="mt-5 border-warning p-[clamp(1.25rem,3vw,2rem)]"
      aria-labelledby="clarification-title"
    >
      <div className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
        A decision is needed
      </div>
      <h2
        id="clarification-title"
        className="font-display text-lg font-semibold tracking-[-0.04em]"
      >
        The question has more than one useful reading.
      </h2>
      <p className="leading-[1.55] text-ink-muted">
        {clarification.question ?? "Choose the interpretation that best matches your intent."}
      </p>
      <div className="flex flex-wrap gap-2">
        {clarification.choices.map((choice) => (
          <button
            key={choice}
            type="button"
            className="rounded-control border border-border bg-surface-muted px-3 py-2 text-left text-sm text-ink focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-2"
            onClick={() => onChange(choice)}
            disabled={disabled}
          >
            {choice}
          </button>
        ))}
      </div>
      <label className="mb-2 mt-5 block text-sm font-bold" htmlFor="clarification">
        Add context
      </label>
      <textarea
        id="clarification"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        disabled={disabled}
        placeholder="Tell the analyst which meaning to use..."
        className="w-full resize-y rounded-control border border-border bg-surface-muted p-4 leading-[1.55] text-ink outline-none focus:border-accent focus:ring-3 focus:ring-accent/20"
      />
      <button
        type="button"
        className="mt-3 min-h-11 rounded-control border-2 border-accent bg-accent px-4 py-3 font-bold text-surface disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-3"
        onClick={onSubmit}
        disabled={disabled || value.trim().length === 0}
      >
        {disabled ? "Sending..." : "Continue with this meaning"}
      </button>
    </Panel>
  );
}
