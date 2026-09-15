import { useEffect, useReducer } from "react";
import "./index.css";
import { queryApi } from "./api/client";
import { ClarificationPanel } from "./components/ClarificationPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { QueryComposer } from "./components/QueryComposer";
import { ResultsPanel } from "./components/ResultsPanel";
import { SqlInspector } from "./components/SqlInspector";
import { WorkflowStatus } from "./components/WorkflowStatus";
import { initialQueryState, queryReducer } from "./state/queryState";

function App() {
  const [state, dispatch] = useReducer(queryReducer, initialQueryState);

  useEffect(() => {
    if (window.location.pathname === "/10") {
      window.history.replaceState({}, "", "/");
    }
  }, []);

  const run = async (action: string, request: () => ReturnType<typeof queryApi.create>) => {
    dispatch({ type: "start", action });
    try {
      dispatch({ type: "success", response: await request() });
    } catch (error) {
      dispatch({
        type: "failure",
        error: error instanceof Error ? error : new Error("The request could not be completed."),
      });
    }
  };

  return (
    <div
      className="min-h-screen min-w-80 bg-canvas bg-[radial-gradient(circle_at_8%_12%,rgb(255_255_255_/_55%),transparent_28%)] font-body text-ink"
      data-design="field-guide"
    >
      <a
        className="fixed left-4 top-0 z-10 -translate-y-[120%] bg-ink px-4 py-3 text-surface focus:translate-y-0 focus:outline-3 focus:outline-accent focus:outline-offset-3"
        href="#workspace"
      >
        Skip to workspace
      </a>
      <main
        id="workspace"
        className="mx-auto grid w-[min(calc(100%-3rem),1320px)] grid-cols-[13rem_minmax(0,1fr)_13rem] gap-[clamp(1.25rem,3vw,3rem)] py-16 pb-12 max-[1050px]:grid-cols-[11rem_minmax(0,1fr)] max-[1050px]:[&>.right-rail]:hidden max-[720px]:flex max-[720px]:w-[min(calc(100%-2rem),1320px)] max-[720px]:flex-col max-[720px]:gap-0 max-[720px]:py-10"
      >
        <div
          className="col-span-full flex items-center justify-between border-b border-border pb-3 text-xs uppercase tracking-[0.08em] text-ink-muted max-[720px]:items-start max-[720px]:flex-col max-[720px]:gap-2"
          aria-label="System context"
        >
          <span className="font-bold text-accent-strong">Schema terrain</span>
          <span>FastAPI / PostgreSQL / read-only</span>
        </div>
        <HistoryPanel
          entries={state.history}
          onSelect={(id) => void run("load", () => queryApi.get(id))}
        />
        <div className="min-w-0 max-[720px]:order-1">
          <section className="mb-10 max-w-3xl">
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
              A transparent question interface
            </p>
            <h1 className="m-0 font-display text-display font-medium tracking-[-0.07em]">
              Ask the source.
              <br />
              <em>Inspect the answer.</em>
            </h1>
            <p className="mt-6 max-w-[31rem] text-md leading-[1.55] text-ink-muted">
              Natural language in. Relevant schema, validated SQL, and grounded evidence out.
            </p>
          </section>
          <QueryComposer
            question={state.question}
            mode={state.executionMode}
            disabled={Boolean(state.activeAction)}
            onQuestion={(value) => dispatch({ type: "question", value })}
            onMode={(value) => dispatch({ type: "mode", value })}
            onSubmit={() =>
              void run("analyze", () => queryApi.create(state.question.trim(), state.executionMode))
            }
          />
          {state.error ? (
            <div
              className="mt-4 border-l-3 border-danger bg-surface-muted px-4 py-3 text-sm leading-[1.45] text-ink-muted"
              role="alert"
            >
              <strong>Request not completed.</strong> {state.error}
            </div>
          ) : null}
          <WorkflowStatus response={state.response} activeAction={state.activeAction} />
          {state.response ? (
            <ClarificationPanel
              response={state.response}
              value={state.clarificationDraft}
              disabled={Boolean(state.activeAction)}
              onChange={(value) => dispatch({ type: "clarification", value })}
              onSubmit={() =>
                void run("clarify", () =>
                  queryApi.clarify(state.response!.query_id, state.clarificationDraft.trim()),
                )
              }
            />
          ) : null}
          {state.response ? (
            <SqlInspector
              response={state.response}
              draft={state.sqlDraft}
              disabled={Boolean(state.activeAction)}
              onDraft={(value) => dispatch({ type: "sql", value })}
              onEdit={() =>
                void run("validate edit", () =>
                  queryApi.edit(state.response!.query_id, state.sqlDraft.trim()),
                )
              }
              onApprove={() =>
                void run("approve", () =>
                  queryApi.approve(
                    state.response!.query_id,
                    state.response!.sql_inspector!.sql_version,
                  ),
                )
              }
              onExecute={() =>
                void run("execute", () => queryApi.execute(state.response!.query_id))
              }
              onRegenerate={() =>
                void run("regenerate", () => queryApi.regenerate(state.response!.query_id))
              }
            />
          ) : null}
          {state.response ? <ResultsPanel response={state.response} /> : null}
        </div>
        <aside
          className="grid content-start gap-4 max-[1050px]:hidden max-[720px]:order-3 max-[720px]:grid"
          aria-label="How your question is handled"
        >
          <div className="border-t-2 border-accent p-4 text-sm leading-[1.5] text-ink-muted">
            <div className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
              How your question is handled
            </div>
            <strong className="block text-ink">Read-only field guide</strong>
            <p className="mt-2 mb-0">A safer path from question to evidence.</p>
          </div>
          {[
            [
              "01",
              "Relevant schema only",
              "The system retrieves source structure relevant to your question, not the entire schema for every request.",
            ],
            [
              "02",
              "Read-only execution",
              "SQL is checked by deterministic backend policy and runs through a read-only source connection.",
            ],
            [
              "03",
              "You stay in control",
              "Review Mode is the default. Inspect the exact SQL, assumptions, limits, and validation state before approving it.",
            ],
            [
              "04",
              "No credentials in the browser",
              "Database URLs, passwords, index credentials, and model keys stay on the backend.",
            ],
          ].map(([number, title, detail]) => (
            <div
              key={number}
              className="border-t border-border pt-4 text-sm leading-[1.5] text-ink-muted"
            >
              <span className="font-code text-xs text-success">{number}</span>
              <strong className="mt-1 block text-ink">{title}</strong>
              <p className="mt-2 mb-0">{detail}</p>
            </div>
          ))}
          <p className="border-t border-border pt-4 text-xs leading-[1.5] text-ink-muted">
            The frontend displays backend decisions. It never authorizes SQL by itself.
          </p>
        </aside>
      </main>
      <footer className="mx-auto flex w-[min(calc(100%-3rem),1320px)] flex-wrap justify-center gap-4 border-t border-border py-4 pb-6 text-xs uppercase tracking-[0.08em] text-ink-muted max-[720px]:w-[min(calc(100%-2rem),1320px)] max-[720px]:items-start max-[720px]:flex-col max-[720px]:gap-2">
        <span>Review Mode is the default.</span>
        <span>Credentials stay on the backend.</span>
        <span>Query state lasts for this session.</span>
      </footer>
    </div>
  );
}

export default App;
