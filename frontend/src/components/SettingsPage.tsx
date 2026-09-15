import { useState } from "react";
import { settingsApi } from "../api/client";
import type { DatabaseConnectionResponse, DatabaseIndexResponse } from "../api/types";
import { Button, CodeBlock, Notice, Panel, SectionHeader, StatusBadge } from "../design-system";

type SettingsPageProps = {
  onBack: () => void;
};

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [url, setUrl] = useState("");
  const [schemaScope, setSchemaScope] = useState("public");
  const [connection, setConnection] = useState<DatabaseConnectionResponse | null>(null);
  const [index, setIndex] = useState<DatabaseIndexResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  async function run(action: string, request: () => Promise<unknown>, success: string) {
    setBusy(action);
    setMessage(null);
    try {
      const result = await request();
      if (result && "host" in Object(result)) setConnection(result as DatabaseConnectionResponse);
      if (result && "source_fingerprint" in Object(result))
        setIndex(result as DatabaseIndexResponse);
      setMessage({ tone: "success", text: success });
    } catch (error) {
      setMessage({
        tone: "danger",
        text:
          error instanceof Error ? error.message : "The settings request could not be completed.",
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen min-w-80 bg-canvas bg-[radial-gradient(circle_at_8%_12%,rgb(255_255_255_/_55%),transparent_28%)] font-body text-ink">
      <a
        className="fixed left-4 top-0 z-10 -translate-y-[120%] bg-ink px-4 py-3 text-surface focus:translate-y-0 focus:outline-3 focus:outline-accent focus:outline-offset-3"
        href="#settings"
      >
        Skip to settings
      </a>
      <main
        id="settings"
        className="mx-auto w-[min(calc(100%-3rem),1080px)] py-10 max-[720px]:w-[min(calc(100%-2rem),1080px)] max-[720px]:py-6"
      >
        <header className="flex items-center justify-between border-b border-border pb-3 max-[560px]:items-start max-[560px]:gap-4">
          <div className="text-xs font-bold uppercase tracking-[0.1em] text-accent-strong">
            Schema terrain / settings
          </div>
          <Button variant="quiet" onClick={onBack}>
            Back to workspace
          </Button>
        </header>

        <section className="grid gap-5 py-12 md:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)] md:items-end">
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
              One local connection
            </p>
            <h1 className="m-0 max-w-3xl font-display text-display font-medium tracking-[-0.07em]">
              Point the field guide at your source.
            </h1>
          </div>
          <p className="m-0 max-w-md text-md leading-[1.55] text-ink-muted">
            Connect a PostgreSQL database with a dedicated read-only role. The running backend keeps
            this connection in memory; it is cleared when the backend restarts.
          </p>
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(18rem,0.9fr)]">
          <div className="grid gap-6">
            <Panel className="p-6 max-[560px]:p-5">
              <SectionHeader eyebrow="01 / source access" title="Database connection" />
              <div className="mt-6 grid gap-5">
                <label className="grid gap-2 text-sm font-semibold" htmlFor="database-url">
                  PostgreSQL connection URL
                  <input
                    id="database-url"
                    type="password"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder="postgresql+psycopg://reader:•••@db.example.com:5432/analytics"
                    autoComplete="off"
                    spellCheck={false}
                    className="min-h-12 rounded-control border border-border bg-canvas px-4 font-code text-sm font-normal text-ink outline-none placeholder:text-ink-muted focus:border-accent focus:ring-2 focus:ring-accent/30"
                  />
                  <span className="text-xs font-normal leading-[1.5] text-ink-muted">
                    This value is sent only to FastAPI and is never displayed back in full or saved
                    in browser storage.
                  </span>
                </label>
                <label className="grid gap-2 text-sm font-semibold" htmlFor="schema-scope">
                  Approved schema scope
                  <input
                    id="schema-scope"
                    type="text"
                    value={schemaScope}
                    onChange={(event) => setSchemaScope(event.target.value)}
                    placeholder="public"
                    autoComplete="off"
                    className="min-h-12 rounded-control border border-border bg-canvas px-4 font-code text-sm font-normal text-ink outline-none placeholder:text-ink-muted focus:border-accent focus:ring-2 focus:ring-accent/30"
                  />
                  <span className="text-xs font-normal leading-[1.5] text-ink-muted">
                    Use a comma-separated list of source schemas. PostgreSQL system schemas are
                    blocked.
                  </span>
                </label>
                <div className="flex flex-wrap gap-3 border-t border-border pt-5">
                  <Button
                    variant="secondary"
                    disabled={Boolean(busy) || !url.trim() || !schemaScope.trim()}
                    onClick={() =>
                      void run(
                        "test",
                        () => settingsApi.testDatabase(url, schemaScope),
                        "Connection verified. The role passed the read-only checks.",
                      )
                    }
                  >
                    {busy === "test" ? "Testing…" : "Test connection"}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={Boolean(busy) || !url.trim() || !schemaScope.trim()}
                    onClick={() =>
                      void run(
                        "save",
                        () => settingsApi.saveDatabase(url, schemaScope),
                        "Connection saved for this backend session.",
                      )
                    }
                  >
                    {busy === "save" ? "Saving…" : "Save connection"}
                  </Button>
                  <Button
                    variant="quiet"
                    disabled={Boolean(busy)}
                    onClick={() =>
                      void run("disconnect", settingsApi.disconnectDatabase, "Source disconnected.")
                    }
                  >
                    Disconnect
                  </Button>
                </div>
                {message ? <Notice tone={message.tone}>{message.text}</Notice> : null}
              </div>
            </Panel>

            <Panel className="p-6 max-[560px]:p-5">
              <SectionHeader eyebrow="02 / local index" title="Schema index" />
              <div className="mt-5 grid gap-4">
                <p className="m-0 text-sm leading-[1.55] text-ink-muted">
                  Indexing reads schema metadata from the active source and writes documents and
                  embeddings only to the local pgvector database. Run it after every database
                  change.
                </p>
                <Button
                  variant="secondary"
                  disabled={Boolean(busy) || !connection}
                  onClick={() =>
                    void run(
                      "index",
                      settingsApi.indexDatabase,
                      "Schema index refreshed successfully.",
                    )
                  }
                >
                  {busy === "index" ? "Indexing schema…" : "Index or refresh schema"}
                </Button>
                {index ? (
                  <div className="grid gap-2 border-t border-border pt-4 text-sm">
                    <div className="flex justify-between gap-4">
                      <span className="text-ink-muted">Status</span>
                      <StatusBadge state="ready">{index.status}</StatusBadge>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="text-ink-muted">Documents</span>
                      <span className="font-code">{index.document_count}</span>
                    </div>
                  </div>
                ) : (
                  <p className="m-0 text-xs text-ink-muted">
                    No indexing result in this settings session.
                  </p>
                )}
              </div>
            </Panel>
          </div>

          <aside className="grid content-start gap-6">
            <Panel className="p-6 max-[560px]:p-5">
              <SectionHeader eyebrow="Connection status" title="Current source" />
              <div className="mt-5 grid gap-3 text-sm">
                {connection ? (
                  <>
                    <StatusBadge state="ready">Read-only verified</StatusBadge>
                    <dl className="grid gap-3 border-t border-border pt-4">
                      <StatusRow label="Host" value={connection.host} />
                      <StatusRow label="Database" value={connection.database ?? "Unknown"} />
                      <StatusRow label="User" value={connection.user ?? "Unknown"} />
                      <StatusRow label="Schemas" value={connection.schemas.join(", ")} />
                      <StatusRow label="Relations" value={String(connection.relation_count)} />
                    </dl>
                  </>
                ) : (
                  <Notice tone="warning">
                    No runtime source is connected. Test and save a read-only PostgreSQL URL to
                    begin.
                  </Notice>
                )}
              </div>
            </Panel>

            <Panel className="p-6 max-[560px]:p-5">
              <SectionHeader eyebrow="Administrator guide" title="How to get a safe URL" />
              <div className="mt-5 grid gap-4 text-sm leading-[1.55] text-ink-muted">
                <p className="m-0">
                  Ask your database administrator for a dedicated login with only connection, schema
                  usage, and select access.
                </p>
                <CodeBlock>{`CREATE ROLE nl2sql_reader LOGIN PASSWORD '<strong-password>';
GRANT CONNECT ON DATABASE <database> TO nl2sql_reader;
GRANT USAGE ON SCHEMA <schema> TO nl2sql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA <schema> TO nl2sql_reader;
REVOKE CREATE ON DATABASE <database> FROM nl2sql_reader;
REVOKE CREATE ON SCHEMA <schema> FROM nl2sql_reader;`}</CodeBlock>
                <p className="m-0">The administrator can then provide a URL in this shape:</p>
                <CodeBlock>
                  postgresql+psycopg://nl2sql_reader:&lt;password&gt;@&lt;host&gt;:5432/&lt;database&gt;
                </CodeBlock>
                <Notice tone="danger">
                  Never use an owner, superuser, or write-capable account. Do not paste this URL
                  into chat, commit it, or share it in screenshots.
                </Notice>
              </div>
            </Panel>
          </aside>
        </div>

        <section className="mt-6 border-t border-border pt-6">
          <SectionHeader eyebrow="Application safeguards" title="Backend-controlled settings" />
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <SettingCard
              title="Review Mode"
              detail="Default execution mode. Approval is required."
            />
            <SettingCard
              title="Read-only policy"
              detail="Writes, DDL, and multi-statement SQL stay blocked."
            />
            <SettingCard
              title="Resource limits"
              detail="Timeout, row, result-size, and retry limits stay on the backend."
            />
          </div>
        </section>
      </main>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="m-0 max-w-[65%] break-words text-right font-code text-xs">{value}</dd>
    </div>
  );
}

function SettingCard({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="border border-dashed border-border bg-surface-muted p-4">
      <strong className="font-display text-sm">{title}</strong>
      <p className="m-0 mt-2 text-xs leading-[1.5] text-ink-muted">{detail}</p>
    </div>
  );
}
