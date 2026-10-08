import { api } from '../api';
import type { Session, Metrics, RecordDetail, RequestSummary, Invitation } from './types';

export class OperationsError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function call<T>(path: string, token?: string, body?: unknown, key?: string): Promise<T> {
  const response = await fetch(`${api.baseUrl}/api/v2${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(key ? { 'Idempotency-Key': key } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({})) as { detail?: string };
    throw new OperationsError(error.detail ?? `Request failed (${response.status})`, response.status);
  }
  return response.json() as Promise<T>;
}
export const operations = {
  session: (persona: string) => call<Session>('/demo/session', undefined, { persona }),
  requests: (token: string) => call<{ requests: RequestSummary[] }>('/requests', token),
  detail: (token: string, id: string) => call<RecordDetail>(`/requests/${id}`, token),
  metrics: (token: string) => call<Metrics>('/metrics', token),
  measurements: (token: string) => call<{ reports: Record<string, any> }>('/measurements', token),
  verify: (token: string, id: string) => call<{ valid: boolean; events: number }>(`/requests/${id}/history/verify`, token),
  submit: (token: string, id: string, content: string, filename = 'access-review-q3.txt', replaces_document_id?: string) => call(`/requests/${id}/documents`, token, { filename, media_type: 'text/plain', content, replaces_document_id }, crypto.randomUUID()),
  invite: (token: string, id: string) => call<Invitation & { token: string }>(`/requests/${id}/invitations`, token, {}),
  invitations: (token: string, id: string) => call<{ invitations: Invitation[] }>(`/requests/${id}/invitations`, token),
  revoke: (token: string, id: string, invitation: string) => call(`/requests/${id}/invitations/${invitation}/revoke`, token, {}),
  accept: (token: string, name: string) => call<Session>('/invitations/accept', undefined, { token, name }),
  reopen: (token: string, id: string, version: number, reason: string) => call<RecordDetail>(`/requests/${id}/reopen`, token, { version, reason }),
  process: (token: string) => call<{ processed: number }>('/demo/process', token, {}),
  review: (token: string, id: string, version: number, decision: string, feedback: string) => call<RecordDetail>(`/requests/${id}/review`, token, { version, decision, feedback }),
};
