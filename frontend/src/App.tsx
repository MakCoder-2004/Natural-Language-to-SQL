import { useEffect, useReducer, useState } from "react";
import "./index.css";
import { queryApi } from "./api/client";
import { ClarificationPanel } from "./components/ClarificationPanel";
import { DesignGallery } from "./components/DesignGallery";
import { HistoryPanel } from "./components/HistoryPanel";
import { QueryComposer } from "./components/QueryComposer";
import { ResultsPanel } from "./components/ResultsPanel";
import { SqlInspector } from "./components/SqlInspector";
import { WorkflowStatus } from "./components/WorkflowStatus";
import { getDesign } from "./designs";
import { initialQueryState, queryReducer } from "./state/queryState";

function routeId() {
  const value = window.location.pathname.replace(/^\//, "").split("/")[0];
  return /^([1-9]|10)$/.test(value) ? value : null;
}

function App() {
  const [designId, setDesignId] = useState(routeId());
  const [state, dispatch] = useReducer(queryReducer, initialQueryState);

  useEffect(() => {
    const onPopState = () => setDesignId(routeId());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (!designId) return <DesignGallery />;
  const design = getDesign(designId);

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

  const openDesign = (id: string) => {
    window.history.pushState({}, "", `/${id}`);
    setDesignId(id);
  };

  return (
    <div className={`app-shell ${design.className}`} data-design={design.id}>
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <header className="topbar">
        <a
          className="brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            window.history.pushState({}, "", "/");
            setDesignId(null);
          }}
        >
          <span className="brand-mark" aria-hidden="true">
            ∴
          </span>
          <span>Query / Grounded</span>
        </a>
        <div className="topbar-meta">
          <span className="design-label">
            {design.category} / {design.name}
          </span>
          <label htmlFor="design-select" className="sr-only">
            Switch design
          </label>
          <select
            id="design-select"
            value={design.id}
            onChange={(event) => openDesign(event.target.value)}
          >
            {Array.from({ length: 10 }, (_, index) => {
              const item = getDesign(String(index + 1));
              return (
                <option value={item.id} key={item.id}>
                  {item.id} / {item.name}
                </option>
              );
            })}
          </select>
        </div>
      </header>
      <div className="design-intro">
        <span>{design.signature}</span>
        <span>FastAPI / PostgreSQL / read-only</span>
      </div>
      <main id="workspace" className="workspace">
        <HistoryPanel
          entries={state.history}
          onSelect={(id) => void run("load", () => queryApi.get(id))}
        />
        <div className="main-column">
          <section className="workspace-heading">
            <p className="eyebrow">A transparent question interface</p>
            <h1>
              Ask the source.
              <br />
              <em>Inspect the answer.</em>
            </h1>
            <p>Natural language in. Relevant schema, validated SQL, and grounded evidence out.</p>
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
            <div className="notice notice-error" role="alert">
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
        <aside className="right-rail" aria-label="Query notes">
          <div className="rail-note">
            <span className="note-glyph">↗</span>
            <strong>Backend is the boundary.</strong>
            <p>The interface displays validation facts. It never authorizes SQL by itself.</p>
          </div>
          <div className="rail-note">
            <span className="note-glyph">⌁</span>
            <strong>Current design</strong>
            <p>{design.description}</p>
            <button type="button" onClick={() => openDesign(String((Number(design.id) % 10) + 1))}>
              Try the next study
            </button>
          </div>
        </aside>
      </main>
      <footer className="footer">
        <span>Review Mode is the default.</span>
        <span>Credentials stay on the backend.</span>
        <span>Query state lasts for this session.</span>
      </footer>
    </div>
  );
}

export default App;
