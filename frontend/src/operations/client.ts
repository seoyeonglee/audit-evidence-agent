import { api } from '../api';
import type { Session, Metrics, RecordDetail, RequestSummary } from './types';

async function call<T>(path: string, token?: string, body?: unknown, key?: string): Promise<T> {
  const response = await fetch(`${api.baseUrl}/api/v2${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(key ? { 'Idempotency-Key': key } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(error.detail ?? `Request failed (${response.status})`);
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
  submit: (token: string, id: string, content: string, filename = 'access-review-q3.txt') => call(`/requests/${id}/documents`, token, { filename, media_type: 'text/plain', content }, crypto.randomUUID()),
  process: (token: string) => call<{ processed: number }>('/demo/process', token, {}),
  review: (token: string, id: string, version: number, decision: string, feedback: string) => call<RecordDetail>(`/requests/${id}/review`, token, { version, decision, feedback }),
};
