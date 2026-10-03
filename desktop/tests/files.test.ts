import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readSelectedEvidence } from "../src/files.js";
test("selected UTF8 file yields bounded content and basename only", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-files-"));
  const p = join(root, "증빙.txt");
  await writeFile(p, "system: 금융시스템\nperiod: 2026-Q3");
  const result = await readSelectedEvidence(p);
  assert.equal(result.filename, "증빙.txt");
  assert.equal(result.content, "system: 금융시스템\nperiod: 2026-Q3");
  assert.equal("path" in result, false);
});
test("symlinks, binary UTF8, unsupported and oversized content denied", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-files-"));
  const p = join(root, "file.txt");
  await writeFile(p, "safe");
  await symlink(p, join(root, "link.txt"));
  await assert.rejects(() => readSelectedEvidence(join(root, "link.txt")));
  await assert.rejects(() => readSelectedEvidence(root));
  await writeFile(p, Buffer.from([255, 254, 0]));
  await assert.rejects(() => readSelectedEvidence(p));
  await writeFile(p, "x".repeat(200001));
  await assert.rejects(() => readSelectedEvidence(p));
  await writeFile(p, "x".repeat(1048577));
  await assert.rejects(() => readSelectedEvidence(p));
  await writeFile(join(root, "run.exe"), "safe");
  await assert.rejects(() => readSelectedEvidence(join(root, "run.exe")));
});

test("supported supplementary Unicode and escaped text stay within documented limits", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-unicode-"));
  const p = join(root, "😀".repeat(58) + ".txt");
  await writeFile(p, "😀".repeat(100001));
  const selected = await readSelectedEvidence(p);
  assert.equal([...selected.content].length, 100001);
});

test("read and report-save failures return path-free errors", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-private-path-"));
  await assert.rejects(
    () => readSelectedEvidence(join(root, "deleted.txt")),
    (error) =>
      error instanceof Error &&
      !error.message.includes(root) &&
      !error.message.includes("ENOENT"),
  );
  const files = await import("../src/files.js");
  assert.equal(typeof files.writeSelectedReport, "function");
  await assert.rejects(
    () => files.writeSelectedReport(root, "{}"),
    (error) =>
      error instanceof Error &&
      !error.message.includes(root) &&
      !error.message.includes("EISDIR"),
  );
});
