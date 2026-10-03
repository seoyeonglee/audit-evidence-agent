import { test } from "node:test";
import assert from "node:assert/strict";
import { validateApiRequest, validateSender } from "../src/security.js";
test("allows only canonical bounded API routes", () => {
  assert.equal(
    validateApiRequest({ method: "GET", path: "/api/v2/agent-runs/abc123" })
      .path,
    "/api/v2/agent-runs/abc123",
  );
  for (const path of [
    "https://evil.example",
    "/api/v2/../secrets",
    "/api/v2/%2e%2e/secrets",
    "/api/v1/reviews/reset",
    "/api/v2/agent-runs/a?format=../../x",
  ])
    assert.throws(() => validateApiRequest({ method: "GET", path }));
  assert.throws(() =>
    validateApiRequest({ method: "DELETE", path: "/api/v2/requests" }),
  );
  assert.throws(() =>
    validateApiRequest({
      method: "POST",
      path: "/api/v2/demo/session",
      body: { persona: "x".repeat(1250001) },
    }),
  );
});
test("rejects subframes and mismatching sender origins", () => {
  const main = { url: "file:///app/index.html" };
  validateSender(
    { senderFrame: main, sender: { mainFrame: main } },
    "file:///app/index.html",
  );
  assert.throws(() =>
    validateSender(
      { senderFrame: { url: "file:///other" }, sender: { mainFrame: main } },
      "file:///app/index.html",
    ),
  );
  assert.throws(() =>
    validateSender(
      { senderFrame: main, sender: { mainFrame: main } },
      "file:///elsewhere",
    ),
  );
});

test("legal escape-heavy evidence fits the bounded transport envelope", () => {
  const content =
    "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0\n" +
    "\n".repeat(110000);
  assert.ok(content.length < 200000);
  const body = { filename: "evidence.txt", media_type: "text/plain", content };
  assert.equal(
    validateApiRequest({
      method: "POST",
      path: "/api/v2/requests/abc/documents",
      body,
    }).body,
    body,
  );
});
