import type { CSSProperties } from "react";
import {
  Button,
  CodeBlock,
  EmptyState,
  Notice,
  SectionHeader,
  StatusBadge,
  TagList,
} from "../design-system";

export function ComponentLibrary() {
  return (
    <main className="component-library">
      <p className="eyebrow">Query / Grounded system reference</p>
      <h1>
        Field Guide
        <br />
        <em>Component Library</em>
      </h1>
      <p className="library-lead">
        The production primitives below define the vocabulary of the Cartographic Field Guide. Query
        features compose these same pieces; they do not invent private visual states.
      </p>
      <section className="library-section">
        <SectionHeader eyebrow="Foundations" title="Color roles" />
        <div className="library-row">
          <span className="token-swatch">
            <i style={{ "--swatch": "#eee7d7" } as CSSProperties} />
            canvas
          </span>
          <span className="token-swatch">
            <i style={{ "--swatch": "#243c4a" } as CSSProperties} />
            ink
          </span>
          <span className="token-swatch">
            <i style={{ "--swatch": "#4c6651" } as CSSProperties} />
            success
          </span>
          <span className="token-swatch">
            <i style={{ "--swatch": "#b86c50" } as CSSProperties} />
            accent
          </span>
        </div>
      </section>
      <section className="library-section">
        <SectionHeader eyebrow="Controls" title="Actions and states" />
        <div className="library-row">
          <Button variant="primary">Primary action</Button>
          <Button variant="secondary">Secondary action</Button>
          <Button variant="quiet">Quiet action</Button>
          <Button variant="danger">Danger action</Button>
        </div>
        <div className="library-row">
          <StatusBadge state="ready">Backend validated</StatusBadge>
          <StatusBadge state="pending">Executing</StatusBadge>
          <StatusBadge state="warning">Review required</StatusBadge>
          <StatusBadge state="danger">Blocked</StatusBadge>
          <StatusBadge state="neutral">Waiting</StatusBadge>
        </div>
      </section>
      <section className="library-section">
        <SectionHeader eyebrow="Feedback" title="Notices and empty states" />
        <Notice tone="success">The statement passed the backend policy checks.</Notice>
        <Notice tone="warning">The displayed result is bounded by the configured limit.</Notice>
        <Notice tone="danger">The exact SQL was rejected and cannot execute.</Notice>
        <EmptyState
          title="No rows matched"
          detail="The query completed, but the source returned no records."
        />
      </section>
      <section className="library-section">
        <SectionHeader eyebrow="Data" title="Technical content" />
        <TagList items={["public.metrics", "public.regions"]} />
        <CodeBlock>SELECT region, growth FROM metrics ORDER BY growth DESC;</CodeBlock>
      </section>
      <p>
        <a href="/">← Return to workspace</a>
      </p>
    </main>
  );
}
