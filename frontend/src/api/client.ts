import { isQueryResponse, type ApiError, type QueryResponse } from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

function createApiError(status: number, body: unknown): ApiError {
  const payload = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const errorBody =
    payload.error && typeof payload.error === "object"
      ? (payload.error as Record<string, unknown>)
      : {};
  const error = new Error(
    typeof errorBody.message === "string"
      ? errorBody.message
      : "The request could not be completed.",
  ) as ApiError;
  error.name = "ApiError";
  error.status = status;
  error.code = typeof errorBody.code === "string" ? errorBody.code : "request_failed";
  error.queryId = typeof payload.query_id === "string" ? payload.query_id : undefined;
  return error;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 45_000);
  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) throw createApiError(response.status, body);
    return body as T;
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      const error = new Error(
        "The request took too long. Try again when the service is ready.",
      ) as ApiError;
      error.name = "ApiError";
      error.status = 408;
      error.code = "request_timeout";
      throw error;
    }
    throw cause;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function queryRequest(path: string, body?: unknown): Promise<QueryResponse> {
  const response = await request<unknown>(
    path,
    body === undefined ? undefined : { method: "POST", body: JSON.stringify(body) },
  );
  if (!isQueryResponse(response)) {
    const error = new Error("The API returned an invalid query response.") as ApiError;
    error.name = "ApiError";
    error.status = 502;
    error.code = "invalid_api_response";
    throw error;
  }
  return response;
}

export const queryApi = {
  create: (question: string, executionMode: "REVIEW" | "AUTO") =>
    queryRequest("/api/query", { question, execution_mode: executionMode }),
  clarify: (queryId: string, clarification: string) =>
    queryRequest(`/api/query/${encodeURIComponent(queryId)}/clarify`, { clarification }),
  edit: (queryId: string, sql: string) =>
    queryRequest(`/api/query/${encodeURIComponent(queryId)}/edit`, { sql }),
  approve: (queryId: string, sqlVersion: string) =>
    queryRequest(`/api/query/${encodeURIComponent(queryId)}/approve`, { sql_version: sqlVersion }),
  execute: (queryId: string) =>
    queryRequest(`/api/query/${encodeURIComponent(queryId)}/execute`, {}),
  regenerate: (queryId: string) =>
    queryRequest(`/api/query/${encodeURIComponent(queryId)}/regenerate`, {}),
  get: (queryId: string) =>
    request<QueryResponse>(`/api/query/${encodeURIComponent(queryId)}`).then((response) => {
      if (!isQueryResponse(response))
        throw new Error("The API returned an invalid query response.");
      return response;
    }),
};
