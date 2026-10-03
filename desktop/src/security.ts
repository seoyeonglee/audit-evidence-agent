import type { ApiRequest } from "./contracts.js";
const id = "[A-Za-z0-9_-]+";
const get = new RegExp(
  `^/api/v2/(?:requests|session|requests/${id}|requests/${id}/agent-runs|agent-runs/${id}(?:/events(?:\\?after=\\d+)?|/report(?:\\?format=(?:json|markdown))?)?)$`,
);
const post = new RegExp(
  `^/api/v2/(?:demo/(?:session|agent-scenario|agent-process|process)|requests/${id}/(?:agent-runs|documents)|agent-runs/${id}/review)$`,
);
export function validateApiRequest(input: unknown): ApiRequest {
  if (!input || typeof input !== "object" || Array.isArray(input))
    throw new Error("Invalid API request");
  const r = input as ApiRequest;
  if (
    typeof r.path !== "string" ||
    r.path.length > 300 ||
    !(
      (r.method === "GET" && get.test(r.path)) ||
      (r.method === "POST" && post.test(r.path))
    )
  )
    throw new Error("Route is not allowed");
  if (
    r.body !== undefined &&
    (r.method !== "POST" ||
      !r.body ||
      typeof r.body !== "object" ||
      Array.isArray(r.body))
  )
    throw new Error("Invalid API body");
  if (JSON.stringify(r.body ?? {}).length > 1250000)
    throw new Error("API body exceeds limit");
  if (
    r.bearerToken !== undefined &&
    (typeof r.bearerToken !== "string" ||
      !/^[A-Za-z0-9_-]{1,512}$/.test(r.bearerToken))
  )
    throw new Error("Invalid bearer token");
  if (
    r.idempotencyKey !== undefined &&
    (typeof r.idempotencyKey !== "string" ||
      !/^[A-Za-z0-9_-]{1,120}$/.test(r.idempotencyKey))
  )
    throw new Error("Invalid idempotency key");
  return {
    method: r.method,
    path: r.path,
    body: r.body,
    bearerToken: r.bearerToken,
    idempotencyKey: r.idempotencyKey,
  };
}
export function validateSender(
  event: {
    senderFrame: { url: string } | null;
    sender: { mainFrame: unknown };
  },
  allowedURL: string,
): void {
  if (
    !event.senderFrame ||
    event.senderFrame !== event.sender.mainFrame ||
    event.senderFrame.url !== allowedURL
  )
    throw new Error("Untrusted IPC sender");
}
