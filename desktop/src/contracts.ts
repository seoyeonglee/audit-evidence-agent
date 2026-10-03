export interface ApiRequest {
  method: "GET" | "POST";
  path: string;
  body?: unknown;
  idempotencyKey?: string;
  bearerToken?: string;
}
export interface SelectedEvidence {
  cancelled: false;
  filename: string;
  media_type: string;
  content: string;
}
