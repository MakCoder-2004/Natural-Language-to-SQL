import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function Panel({
  children,
  className = "",
  ...props
}: { children: ReactNode; className?: string } & HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={`rounded-panel border border-border bg-surface shadow-panel ${className}`}
      {...props}
    >
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
    <div className="flex items-center justify-between gap-4">
      <div>
        {eyebrow ? (
          <div className="mb-2 text-xs font-bold uppercase tracking-[0.13em] text-accent-strong">
            {eyebrow}
          </div>
        ) : null}
        <h2 className="font-display text-lg font-semibold tracking-[-0.04em]">{title}</h2>
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
  const colors = {
    ready: "text-success",
    pending: "text-warning",
    warning: "text-warning",
    danger: "text-danger",
    neutral: "text-ink-muted",
  };
  return (
    <span
      className={`inline-flex w-fit rounded-pill border border-current px-3 py-2 text-xs font-bold uppercase tracking-[0.07em] ${colors[state]}`}
    >
      {children}
    </span>
  );
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
    <div
      className={`border-l-3 border-border-strong bg-surface-muted px-4 py-3 text-ink-muted leading-[1.5] ${
        tone === "warning"
          ? "border-warning"
          : tone === "danger"
            ? "border-danger"
            : tone === "success"
              ? "border-success"
              : ""
      }`}
      {...props}
    >
      {children}
    </div>
  );
}

export function TagList({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {items.length ? (
        items.map((item) => (
          <li
            key={item}
            className="rounded-control border border-border px-3 py-2 text-sm text-ink-muted"
          >
            {item}
          </li>
        ))
      ) : (
        <li className="rounded-control border border-border px-3 py-2 text-sm text-ink-muted">
          None reported
        </li>
      )}
    </ul>
  );
}

export function CodeBlock({ children }: { children: ReactNode }) {
  return (
    <pre className="overflow-x-auto bg-code-background p-5 font-code text-sm leading-[1.65] whitespace-pre-wrap">
      <code>{children}</code>
    </pre>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="grid gap-2 border border-dashed border-border p-8 text-center text-ink-muted">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}
