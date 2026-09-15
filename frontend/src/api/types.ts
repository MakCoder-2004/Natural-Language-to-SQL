export type ExecutionMode = "REVIEW" | "AUTO";

export type QueryState =
  | "ANALYZING"
  | "RETRIEVING_SCHEMA"
  | "GENERATING_SQL"
  | "VALIDATING_SQL"
  | "CLARIFICATION_REQUIRED"
  | "READY_FOR_REVIEW"
  | "APPROVED"
  | "EXECUTING"
  | "COMPLETED"
  | "FAILED";

export type Visualization = {
  kind: string;
  x_column: string | null;
  y_columns: string[];
  category_column: string | null;
  reason: string;
};

export type ErrorBody = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type Validation = {
  passed: boolean;
  sql_hash: string;
  referenced_schemas: string[];
  referenced_relations: string[];
  referenced_columns: string[];
  blocking_errors: string[];
  warnings: string[];
  applied_limits: string[];
  read_only: boolean;
  single_statement: boolean;
};

export type SqlInspector = {
  sql: string;
  original_sql: string | null;
  sql_version: string;
  interpretation: string;
  tables_used: string[];
  assumptions: string[];
  validation_passed: boolean;
  blocking_errors: string[];
  read_only: boolean;
  approved_source: boolean;
  single_statement: boolean;
  applied_limits: string[];
  warnings: string[];
  approval_required: boolean;
  approved: boolean;
  stale_approval: boolean;
};

export type QueryResult = {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  returned_row_count: number;
  truncated: boolean;
  result_bytes: number;
  warnings: string[];
  executed_sql_hash: string;
};

export type GroundedAnswer = {
  answer: string;
  caveats: string[];
  evidence_summary: string;
};

export type QueryResponse = {
  query_id: string;
  pipeline_run_id: string;
  question: string;
  execution_mode: ExecutionMode;
  status: QueryState;
  clarification: {
    question: string | null;
    choices: string[];
  } | null;
  sql_inspector: SqlInspector | null;
  validation: Validation | null;
  result: QueryResult | null;
  answer: GroundedAnswer | null;
  visualization: Visualization | null;
  warnings: string[];
  error: ErrorBody | null;
  created_at: string;
};

export type QueryCreateRequest = {
  question: string;
  execution_mode: ExecutionMode;
};

export type ApiError = Error & {
  status: number;
  code: string;
  queryId?: string;
};

export type DatabaseConnectionResponse = {
  connected: boolean;
  host: string;
  port: number | null;
  database: string | null;
  user: string | null;
  schemas: string[];
  relation_count: number;
  read_only_verified: boolean;
};

export type DatabaseDiscoveryResponse = {
  schemas: string[];
};

export type DatabaseIndexResponse = {
  status: string;
  source_fingerprint: string;
  document_count: number;
  embedding_count: number;
  indexed_at: string | null;
};

export function isQueryResponse(value: unknown): value is QueryResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Partial<QueryResponse>;
  return (
    typeof response.query_id === "string" &&
    typeof response.question === "string" &&
    typeof response.status === "string" &&
    (response.execution_mode === "REVIEW" || response.execution_mode === "AUTO")
  );
}
