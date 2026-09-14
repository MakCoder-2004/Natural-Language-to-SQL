import "./index.css";

function App() {
  return (
    <main className="app-shell">
      <section className="hero" aria-labelledby="app-title">
        <p className="eyebrow">Safe schema-aware analytics</p>
        <h1 id="app-title">Ask your PostgreSQL data a question.</h1>
        <p className="intro">
          The query workspace is being prepared. Natural-language questions will be routed through a
          reviewed, read-only SQL workflow.
        </p>
        <div className="status-card" role="status">
          <span className="status-dot" aria-hidden="true" />
          Foundation services are ready to be connected.
        </div>
      </section>
    </main>
  );
}

export default App;
