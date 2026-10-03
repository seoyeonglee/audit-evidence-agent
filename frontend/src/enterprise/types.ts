export interface Session {
  token: string;
  name: string;
  role: string;
  tenant_id: string;
}
export interface EvidenceRequest {
  id: string;
  title: string;
  version: number;
  status: string;
}
export interface Run {
  id: string;
  status: string;
  request_id: string;
  snapshot_version: number;
  current_version?: number;
  stale?: boolean;
  provider: string;
  attempts: number;
  error?: string;
  snapshot: {
    title: string;
    control_id: string;
    period: string;
    canonical: {
      complete: boolean;
      fields: Record<
        string,
        { value: string | number; source: { quote: string; line: number } }
      >;
    };
    documents: { id: string; filename: string; digest: string }[];
  };
  assessment: {
    summary?: string;
    recommendation?: string;
    missing_evidence?: string[];
    citations?: string[];
  };
  grounding: { valid?: boolean; checked_sources?: number; errors?: string[] };
  events: {
    sequence: number;
    node: string;
    outcome: string;
    duration_ms: number;
  }[];
  review?: { decision: string; feedback: string; reviewer: string };
  report?: unknown;
}
