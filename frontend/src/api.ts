import type { Detail, Overview } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  baseUrl: API_BASE,
  overview: () => request<Overview>("/api/v1/overview"),
  detail: (controlId: string) => request<Detail>(`/api/v1/controls/${controlId}`),
  review: (
    controlId: string,
    decision: "approve" | "needs_changes" | "reject",
    feedback: string,
  ) =>
    request<{ review: Detail["review"] }>(`/api/v1/controls/${controlId}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, feedback, reviewer: "portfolio-reviewer" }),
    }),
};
