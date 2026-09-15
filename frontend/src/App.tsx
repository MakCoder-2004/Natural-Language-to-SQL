import { useEffect, useReducer, useState } from "react";
import "./index.css";
import { queryApi } from "./api/client";
import { ClarificationPanel } from "./components/ClarificationPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { QueryComposer } from "./components/QueryComposer";
import { ResultsPanel } from "./components/ResultsPanel";
import { SettingsPage } from "./components/SettingsPage";
import { SqlInspector } from "./components/SqlInspector";
import { WorkflowStatus } from "./components/WorkflowStatus";
import { initialQueryState, queryReducer } from "./state/queryState";

function App() {
  const [state, dispatch] = useReducer(queryReducer, initialQueryState);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [route, setRoute] = useState(window.location.pathname);

  useEffect(() => {
    if (window.location.pathname === "/10") {
      window.history.replaceState({}, "", "/");
    }
  }, []);

  useEffect(() => {
    const onPopState = () => setRoute(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (route === "/settings") {
    return (
      <SettingsPage
        onBack={() => {
          window.history.pushState({}, "", "/");
          setRoute("/");
        }}
      />
    );
  }

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
        className={`mx-auto grid w-[min(calc(100%-3rem),1320px)] gap-[clamp(1.5rem,3vw,3rem)] py-16 pb-12 max-[720px]:flex max-[720px]:w-[min(calc(100%-2rem),1320px)] max-[720px]:flex-col max-[720px]:gap-0 max-[720px]:py-10 ${historyOpen ? "grid-cols-[19rem_minmax(0,1fr)] max-[1050px]:grid-cols-[16rem_minmax(0,1fr)]" : "grid-cols-[minmax(0,56rem)] justify-center"}`}
      >
        <div
          className="col-span-full flex items-center justify-between border-b border-border pb-3 text-xs uppercase tracking-[0.08em] text-ink-muted max-[720px]:items-start max-[720px]:flex-col max-[720px]:gap-2"
          aria-label="System context"
        >
          <span className="font-bold text-accent-strong">Schema terrain</span>
          <div className="flex items-center gap-4 max-[720px]:flex-wrap">
            <div className="flex items-center gap-4">
              <span>FastAPI / PostgreSQL / read-only</span>
              <button
                type="button"
                className="rounded-control border border-border bg-transparent px-3 py-2 text-xs font-bold uppercase tracking-[0.06em] text-ink-muted transition-colors hover:border-accent hover:text-accent-strong focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-2"
                onClick={() => {
                  window.history.pushState({}, "", "/settings");
                  setRoute("/settings");
                }}
              >
                Settings
              </button>
            </div>
            {!historyOpen ? (
              <button
                type="button"
                className="rounded-control border border-border bg-transparent px-3 py-2 text-xs font-bold uppercase tracking-[0.06em] text-ink-muted transition-colors hover:border-accent hover:text-accent-strong focus-visible:outline-3 focus-visible:outline-accent focus-visible:outline-offset-2"
                onClick={() => setHistoryOpen(true)}
              >
                Show history
              </button>
            ) : null}
          </div>
        </div>
        {historyOpen ? (
          <HistoryPanel
            entries={state.history}
            onSelect={(id) => void run("load", () => queryApi.get(id))}
            onClose={() => setHistoryOpen(false)}
          />
        ) : null}
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
          {state.response?.error ? (
            <div
              className="mt-4 border-l-3 border-danger bg-surface-muted px-4 py-3 text-sm leading-[1.45] text-ink-muted"
              role="alert"
            >
              <strong>Workflow failed.</strong> {state.response.error.message} (
              {state.response.error.code})
            </div>
          ) : null}
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
      </main>
    </div>
  );
}

export default App;
