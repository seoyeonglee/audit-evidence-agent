// Capture actual completed reports, never synthesize pass results.
import { chromium } from "../frontend/node_modules/@playwright/test/index.mjs";
import { readFile, writeFile, mkdir, stat } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { resolve, extname, sep } from "node:path";
const root = resolve("."),
  out = resolve(process.argv[2] ?? "docs/screenshots");
const junit = JSON.parse(
  execFileSync(
    process.env.PYTHON_BIN ?? "python",
    [
      "-c",
      `import json,xml.etree.ElementTree as E
r=E.parse('docs/reports/enterprise-backend.xml').getroot()
c=r.findall('.//testcase')
print(json.dumps({'total':len(c),'passed':sum(not any(x.tag in ('failure','error','skipped') for x in t) for t in c),'skipped':sum(t.find('skipped') is not None for t in c),'failed':sum(t.find('failure') is not None or t.find('error') is not None for t in c),'cases':[{'name':t.attrib['name'],'class':t.attrib.get('classname'),'seconds':t.attrib.get('time'),'status':'SKIP' if t.find('skipped') is not None else 'FAIL' if t.find('failure') is not None or t.find('error') is not None else 'PASS'} for t in c]}))`,
    ],
    { encoding: "utf8" },
  ),
);
const esc = (s) =>
  String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
await writeFile(
  "docs/reports/backend-results.html",
  `<!doctype html><html><meta charset="utf-8"><title>Actual pytest JUnit results</title><style>body{background:#101722;color:#dce5f1;font:16px system-ui;margin:48px}h1{font-size:32px}header{border-bottom:1px solid #435063;padding-bottom:24px}strong{color:#70dbaf}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #263448;padding:12px}small{color:#acb9cb}</style><header><small>ACTUAL TEST REPORT / JUNIT ARTIFACT</small><h1>Backend behavior &amp; security</h1><p><strong>${junit.passed} passed</strong> · ${junit.failed} failed · ${junit.skipped} skipped / ${junit.total} collected</p><p>Python 3.12 · pytest · SQLite local execution · offline heuristic</p><p>PostgreSQL-only tests skipped locally. Real PostgreSQL service runs separately in CI.</p><a href="enterprise-backend.xml">Source JUnit XML</a></header><table><tr><th>Result</th><th>Suite / test</th><th>Seconds</th></tr>${junit.cases.map((c) => `<tr><td>${c.status}</td><td>${esc(c.class)}<br>${esc(c.name)}</td><td>${esc(c.seconds)}</td></tr>`).join("")}</table></html>`,
);
const server = createServer(async (req, res) => {
  try {
    const p = resolve(
      root,
      "." + decodeURIComponent(new URL(req.url, "http://localhost").pathname),
    );
    if (!p.startsWith(root + sep) || !/playwright-report|docs\/reports/.test(p))
      throw Error();
    const body = await readFile(p);
    res.setHeader(
      "Content-Type",
      extname(p) === ".html"
        ? "text/html"
        : extname(p) === ".js"
          ? "application/javascript"
          : extname(p) === ".css"
            ? "text/css"
            : "application/octet-stream",
    );
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const browser = await chromium.launch({ headless: true });
try {
  await mkdir(out, { recursive: true });
  const page = await browser.newPage({
    viewport: { width: 1512, height: 1120 },
  });
  for (const [kind, path] of [
    ["browser", "frontend/playwright-report/index.html"],
    ["desktop", "desktop/playwright-report/index.html"],
    ["backend", "docs/reports/backend-results.html"],
  ]) {
    await stat(path);
    await page.goto(`http://127.0.0.1:${server.address().port}/${path}`, {
      waitUntil: "networkidle",
    });
    if (kind !== "backend") {
      await page
        .getByText(/^Passed\s*\d+$/)
        .first()
        .waitFor();
    }
    await page.screenshot({
      path: resolve(out, `tests-${kind}.png`),
      fullPage: kind !== "backend",
    });
    console.log("Captured actual report:", kind);
  }
} finally {
  await browser.close();
  server.close();
}
