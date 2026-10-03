import { api } from "../api";
export interface DesktopBridge {
  runtimeStatus(): Promise<{ status: string; profile: string }>;
  apiRequest(input: {
    method: "GET" | "POST";
    path: string;
    body?: unknown;
    idempotencyKey?: string;
    bearerToken?: string;
  }): Promise<unknown>;
  selectEvidence(): Promise<{
    cancelled: boolean;
    filename?: string;
    media_type?: string;
    content?: string;
  }>;
  saveReport(runId: string): Promise<{ saved: boolean }>;
}
declare global {
  interface Window {
    auditDesktop?: DesktopBridge;
  }
}
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  method: "GET" | "POST",
  path: string,
  token?: string,
  body?: unknown,
  key?: string,
): Promise<T> {
  if (window.auditDesktop) {
    const data = await window.auditDesktop.apiRequest({
      method,
      path,
      body,
      idempotencyKey: key,
      bearerToken: token,
    });
    if (data && typeof data === "object" && "$auditError" in data) {
      const e = (data as { $auditError: { status: number; message: string } })
        .$auditError;
      throw new ApiError(e.status, e.message);
    }
    return data as T;
  }
  const res = await fetch(api.baseUrl + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.detail || `API error ${res.status}`);
  }
  return (await res.json()) as T;
}
