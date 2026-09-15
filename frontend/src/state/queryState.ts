import type { ApiError, ExecutionMode, QueryResponse } from "../api/types";

export type HistoryEntry = Pick<
  QueryResponse,
  "query_id" | "question" | "status" | "execution_mode" | "created_at"
>;

export type QueryUiState = {
  question: string;
  executionMode: ExecutionMode;
  response: QueryResponse | null;
  sqlDraft: string;
  clarificationDraft: string;
  activeAction: string | null;
  error: string | null;
  history: HistoryEntry[];
};

export const initialQueryState: QueryUiState = {
  question: "",
  executionMode: "REVIEW",
  response: null,
  sqlDraft: "",
  clarificationDraft: "",
  activeAction: null,
  error: null,
  history: [],
};

type Action =
  | { type: "question"; value: string }
  | { type: "mode"; value: ExecutionMode }
  | { type: "clarification"; value: string }
  | { type: "sql"; value: string }
  | { type: "start"; action: string }
  | { type: "success"; response: QueryResponse }
  | { type: "failure"; error: ApiError | Error }
  | { type: "history"; response: QueryResponse };

function toHistory(response: QueryResponse): HistoryEntry {
  return {
    query_id: response.query_id,
    question: response.question,
    status: response.status,
    execution_mode: response.execution_mode,
    created_at: response.created_at,
  };
}

export function queryReducer(state: QueryUiState, action: Action): QueryUiState {
  switch (action.type) {
    case "question":
      return { ...state, question: action.value, error: null };
    case "mode":
      return { ...state, executionMode: action.value, error: null };
    case "clarification":
      return { ...state, clarificationDraft: action.value };
    case "sql":
      return { ...state, sqlDraft: action.value };
    case "start":
      return { ...state, activeAction: action.action, error: null };
    case "success": {
      const history = [
        toHistory(action.response),
        ...state.history.filter((item) => item.query_id !== action.response.query_id),
      ];
      return {
        ...state,
        response: action.response,
        question: action.response.question,
        executionMode: action.response.execution_mode,
        sqlDraft: action.response.sql_inspector?.sql ?? "",
        activeAction: null,
        error: null,
        history,
      };
    }
    case "history":
      return {
        ...state,
        history: [
          toHistory(action.response),
          ...state.history.filter((item) => item.query_id !== action.response.query_id),
        ],
      };
    case "failure":
      return {
        ...state,
        activeAction: null,
        error: action.error.message || "The request could not be completed.",
      };
  }
}
