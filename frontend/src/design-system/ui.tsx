import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function Panel({
  children,
  className = "",
  ...props
}: { children: ReactNode; className?: string } & HTMLAttributes<HTMLElement>) {
  return (
    <section className={`ui-panel ${className}`} {...props}>
      {children}
    </section>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="ui-section-header">
      <div>
        {eyebrow ? <div className="section-kicker">{eyebrow}</div> : null}
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}

export function Button({
  variant = "secondary",
  children,
  ...props
}: {
  variant?: "primary" | "secondary" | "quiet" | "danger";
  children: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`ui-button ui-button-${variant}`} {...props}>
      {children}
    </button>
  );
}

export function StatusBadge({
  state,
  children,
}: {
  state: "ready" | "pending" | "warning" | "danger" | "neutral";
  children: ReactNode;
}) {
  return <span className={`ui-status ui-status-${state}`}>{children}</span>;
}

export function Notice({
  tone = "neutral",
  children,
  ...props
}: {
  tone?: "neutral" | "warning" | "danger" | "success";
  children: ReactNode;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`ui-notice ui-notice-${tone}`} {...props}>
      {children}
    </div>
  );
}

export function TagList({ items }: { items: string[] }) {
  return (
    <ul className="ui-tag-list">
      {items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>None reported</li>}
    </ul>
  );
}

export function CodeBlock({ children }: { children: ReactNode }) {
  return (
    <pre className="ui-code-block">
      <code>{children}</code>
    </pre>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="ui-empty-state">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}
