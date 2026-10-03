import type { ApiRequest } from "./contracts.js";
import { validateApiRequest } from "./security.js";
export class ApiProxyError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function proxyApi(
  input: unknown,
  baseURL: string,
  secret: string,
): Promise<unknown> {
  const r = validateApiRequest(input);
  const base = new URL(baseURL);
  if (base.hostname !== "127.0.0.1" || base.protocol !== "http:")
    throw new Error("Local API required");
  const response = await fetch(baseURL + r.path, {
    method: r.method,
    signal: AbortSignal.timeout(15000),
    headers: {
      "Content-Type": "application/json",
      "X-Desktop-Secret": secret,
      ...(r.bearerToken ? { Authorization: `Bearer ${r.bearerToken}` } : {}),
      ...(r.idempotencyKey ? { "Idempotency-Key": r.idempotencyKey } : {}),
    },
    ...(r.body !== undefined ? { body: JSON.stringify(r.body) } : {}),
  });
  const text = await response.text();
  if (text.length > 6000000) throw new Error("API response exceeds limit");
  const data = JSON.parse(text);
  if (!response.ok)
    throw new ApiProxyError(
      response.status,
      typeof data.detail === "string"
        ? data.detail
        : `Local API error ${response.status}`,
    );
  if (!data || typeof data !== "object" || Array.isArray(data))
    throw new Error("Unexpected API response");
  return data;
}
