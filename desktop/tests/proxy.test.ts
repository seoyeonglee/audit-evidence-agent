import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { proxyApi, ApiProxyError } from "../src/proxy.js";
test("local HTTP authentication status survives the trusted transport", async () => {
  const server = createServer((req, res) => {
    assert.equal(req.headers["x-desktop-secret"], "main-only");
    res.writeHead(401, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ detail: "Invalid bearer token" }));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  try {
    const a = server.address();
    assert.ok(a && typeof a === "object");
    await assert.rejects(
      () =>
        proxyApi(
          { method: "GET", path: "/api/v2/requests" },
          `http://127.0.0.1:${a.port}`,
          "main-only",
        ),
      (e) =>
        e instanceof ApiProxyError &&
        e.status === 401 &&
        !e.message.includes("main-only"),
    );
  } finally {
    await new Promise<void>((r) => server.close(() => r()));
  }
});
