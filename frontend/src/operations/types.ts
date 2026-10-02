export type FieldFact = { value: string | number; source: { document_id: string; digest: string; line: number; quote: string }; method: string };
export type Canonical = { fields?: Record<string, FieldFact>; exceptions?: { code: string; message: string }[]; complete?: boolean; provider?: string };
export type RequestSummary = { id: string; title: string; control_id: string; tenant_id: string; period: string; status: string; version: number; owner_id: string; canonical: Canonical };
export type RecordDetail = RequestSummary & {
  documents: { id: string; filename: string; digest: string; submitted_by: string; extraction: unknown }[];
  jobs: { id: string; document_id: string; status: string; attempts: number; error: string | null }[];
  events: { id: number; event_type: string; actor: string; created_at: string; event_hash: string; payload: Record<string, unknown> }[];
};
export type Session = { token: string; name: string; role: string; tenant_id: string };
export type Metrics = { jobs: number; requests: number; queue: Record<string, number>; retry_attempts: number; approved: number; storage: string };
