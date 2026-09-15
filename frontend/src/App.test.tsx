import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const readyResponse = {
  query_id: "query-1",
  pipeline_run_id: "run-1",
  question: "Which regions grew fastest?",
  execution_mode: "REVIEW",
  status: "READY_FOR_REVIEW",
  clarification: null,
  sql_inspector: {
    sql: "SELECT region, growth FROM metrics ORDER BY growth DESC",
    original_sql: null,
    sql_version: "version-1",
    interpretation: "Compare regional growth.",
    tables_used: ["public.metrics"],
    assumptions: [],
    validation_passed: true,
    blocking_errors: [],
    read_only: true,
    approved_source: true,
    single_statement: true,
    applied_limits: ["max 100 rows"],
    warnings: [],
    approval_required: true,
    approved: false,
    stale_approval: false,
  },
  validation: {
    passed: true,
    sql_hash: "hash-1",
    referenced_schemas: ["public"],
    referenced_relations: ["metrics"],
    referenced_columns: ["region", "growth"],
    blocking_errors: [],
    warnings: [],
    applied_limits: ["max 100 rows"],
    read_only: true,
    single_statement: true,
  },
  result: null,
  answer: null,
  visualization: null,
  warnings: [],
  error: null,
  created_at: "2026-09-15T12:00:00Z",
};

function response(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
}

function withChanges(changes: Record<string, unknown>) {
  return { ...readyResponse, ...changes };
}

describe("Milestone 10 application", () => {
  beforeEach(() => window.history.replaceState({}, "", "/"));
  afterEach(() => vi.restoreAllMocks());

  it("renders the field guide as the canonical production workspace", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /ask the source/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/system context/i)).toHaveTextContent(/schema terrain/i);
    expect(screen.getByLabelText(/system context/i)).toHaveTextContent(
      /fastapi \/ postgresql \/ read-only/i,
    );
    expect(
      screen.getByRole("complementary", { name: /how your question is handled/i }),
    ).toHaveTextContent(
      /relevant schema only|read-only execution|you stay in control|no credentials in the browser/i,
    );
    expect(screen.queryByText(/component library/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/switch design/i)).not.toBeInTheDocument();
  });

  it("normalizes the former design route to the canonical root", () => {
    window.history.replaceState({}, "", "/10");
    render(<App />);
    expect(screen.getByRole("heading", { name: /ask the source/i })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("keeps run modes equal and explains the selected execution path", () => {
    render(<App />);
    const review = screen.getByRole("button", { name: "Review first" });
    const auto = screen.getByRole("button", { name: "Auto run" });
    expect(review).toHaveAttribute("aria-pressed", "true");
    expect(auto).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText(/inspect and approve the exact sql/i)).toBeInTheDocument();

    fireEvent.click(auto);
    expect(review).toHaveAttribute("aria-pressed", "false");
    expect(auto).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/backend validation still applies/i)).toBeInTheDocument();
  });

  it("does not expose the component library as a production route", () => {
    window.history.replaceState({}, "", "/library");
    render(<App />);
    expect(screen.getByRole("heading", { name: /ask the source/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /field guide component library/i }),
    ).not.toBeInTheDocument();
  });

  it("completes the first Review Mode step using backend response data", async () => {
    window.history.replaceState({}, "", "/1");
    const fetchMock = vi.fn().mockResolvedValue(response(readyResponse));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByLabelText(/natural-language question/i), {
      target: { value: readyResponse.question },
    });
    fireEvent.click(screen.getByRole("button", { name: /review question/i }));

    await waitFor(() =>
      expect(screen.getByText(readyResponse.sql_inspector.sql)).toBeInTheDocument(),
    );
    expect(screen.getByText(/backend validated/i)).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toHaveTextContent(/review mode is the default/i);
    expect(screen.queryByText(/database password|connection url/i)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/query",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("keeps execution unavailable while clarification is outstanding", async () => {
    window.history.replaceState({}, "", "/2");
    const clarificationResponse = withChanges({
      status: "CLARIFICATION_REQUIRED",
      clarification: {
        question: "Which period should be compared?",
        choices: ["Last month", "Last quarter"],
      },
      sql_inspector: null,
    });
    const fetchMock = vi.fn().mockResolvedValue(response(clarificationResponse));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.change(screen.getByLabelText(/natural-language question/i), {
      target: { value: readyResponse.question },
    });
    fireEvent.click(screen.getByRole("button", { name: /review question/i }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /more than one useful reading/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /execute query/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /last quarter/i }));
    expect(screen.getByLabelText(/add context/i)).toHaveValue("Last quarter");
  });

  it("renders normalized result values as text and communicates truncation", async () => {
    window.history.replaceState({}, "", "/8");
    const completedResponse = withChanges({
      status: "COMPLETED",
      sql_inspector: {
        ...readyResponse.sql_inspector,
        approval_required: false,
        approved: true,
      },
      result: {
        columns: ["region", "growth"],
        rows: [["<b>North</b>", 42]],
        row_count: 120,
        returned_row_count: 1,
        truncated: true,
        result_bytes: 80,
        warnings: [],
        executed_sql_hash: "hash-completed",
      },
      answer: {
        answer: "North led growth.",
        caveats: [],
        evidence_summary: "Based on the returned rows.",
      },
      visualization: {
        kind: "bar",
        x_column: "region",
        y_columns: ["growth"],
        category_column: null,
        reason: "A bar chart fits the comparison.",
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(completedResponse)));
    render(<App />);
    fireEvent.change(screen.getByLabelText(/natural-language question/i), {
      target: { value: readyResponse.question },
    });
    fireEvent.click(screen.getByRole("button", { name: /review question/i }));
    await waitFor(() =>
      expect(screen.getByRole("cell", { name: "<b>North</b>" })).toBeInTheDocument(),
    );
    expect(screen.getByText(/not the complete dataset/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /chart of growth by region/i })).toBeInTheDocument();
  });

  it("shows a safe error and restores controls after a failed request", async () => {
    window.history.replaceState({}, "", "/10");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Service unavailable")));
    render(<App />);
    fireEvent.change(screen.getByLabelText(/natural-language question/i), {
      target: { value: "Show the latest report" },
    });
    fireEvent.click(screen.getByRole("button", { name: /review question/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/service unavailable/i),
    );
    expect(screen.getByRole("button", { name: /review question/i })).toBeEnabled();
  });
});
