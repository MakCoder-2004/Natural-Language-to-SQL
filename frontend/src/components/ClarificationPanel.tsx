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
    <Panel className="clarification panel" aria-labelledby="clarification-title">
      <div className="section-kicker">A decision is needed</div>
      <h2 id="clarification-title">The question has more than one useful reading.</h2>
      <p>{clarification.question ?? "Choose the interpretation that best matches your intent."}</p>
      <div className="choice-list">
        {clarification.choices.map((choice) => (
          <button key={choice} type="button" onClick={() => onChange(choice)} disabled={disabled}>
            {choice}
          </button>
        ))}
      </div>
      <label htmlFor="clarification">Add context</label>
      <textarea
        id="clarification"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        disabled={disabled}
        placeholder="Tell the analyst which meaning to use..."
      />
      <button
        type="button"
        className="primary-action"
        onClick={onSubmit}
        disabled={disabled || value.trim().length === 0}
      >
        {disabled ? "Sending..." : "Continue with this meaning"}
      </button>
    </Panel>
  );
}
