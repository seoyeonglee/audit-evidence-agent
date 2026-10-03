import { test, expect, _electron as electron } from "@playwright/test";
import { mkdtemp, writeFile, readFile, mkdir, chmod } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
const screenshots = resolve("../docs/screenshots");
async function launch(root: string, python = "python") {
  const app = await electron.launch({
    executablePath: process.env.AUDIT_ELECTRON_APP,
    args: process.env.AUDIT_ELECTRON_APP
      ? ["--no-sandbox"]
      : [".", "--no-sandbox"],
    env: {
      ...process.env,
      AUDIT_USER_DATA: root,
      AUDIT_PYTHON: python,
      DISPLAY: process.env.DISPLAY ?? "127.0.0.1:101",
    },
    timeout: 60000,
  });
  const page = await app.firstWindow();
  await expect(
    page.getByRole("heading", { name: "Agent / Runtime" }),
  ).toBeVisible();
  return { app, page };
}
test("real Electron: persisted interruption survives full app and backend restart", async () => {
  await mkdir(screenshots, { recursive: true });
  const root = await mkdtemp(join(tmpdir(), "audit-desktop-"));
  let { app, page } = await launch(root);
  expect(
    await page.evaluate(() => ({
      require: typeof (window as any).require,
      process: typeof (window as any).process,
    })),
  ).toEqual({ require: "undefined", process: "undefined" });
  await page.getByRole("button", { name: "Create demo request" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  const run = await page.locator(".agent-footer span").first().textContent();
  await page.screenshot({
    path: join(screenshots, "desktop-waiting-review.png"),
    fullPage: true,
  });
  await app.close();
  ({ app, page } = await launch(root));
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  await expect(page.locator(".agent-footer span").first()).toHaveText(run!);
  await page.screenshot({
    path: join(screenshots, "desktop-recovered.png"),
    fullPage: true,
  });
  await page
    .getByLabel("Reviewer feedback")
    .fill(
      "Restored from disk after app and sidecar restart. Exact sources verified.",
    );
  await page
    .getByRole("button", { name: "Approve record", exact: true })
    .click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("completed");
  await page.screenshot({
    path: join(screenshots, "desktop-approved.png"),
    fullPage: true,
  });
  await app.evaluate(({ dialog }, path) => {
    dialog.showSaveDialog = async () => ({ canceled: false, filePath: path });
  }, root);
  await page.getByRole("button", { name: "Export report" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Report could not be saved",
  );
  expect(await page.getByRole("alert").innerText()).not.toContain(root);
  const output = join(root, "review-report.json");
  await app.evaluate(({ dialog }, path) => {
    dialog.showSaveDialog = async () => ({ canceled: false, filePath: path });
  }, output);
  await page.getByRole("button", { name: "Export report" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "Report saved to the selected file.",
  );
  expect(JSON.parse(await readFile(output, "utf8")).review.decision).toBe(
    "approve",
  );
  await expect(
    page.evaluate(async () => {
      try {
        await window.auditDesktop!.apiRequest({
          method: "GET",
          path: "https://example.com",
        });
        return false;
      } catch {
        return true;
      }
    }),
  ).resolves.toBe(true);
  await app.close();
});
test("real Electron: selected local file import uses dialog-owned path", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-import-"));
  const file = join(root, "local-evidence.txt");
  await writeFile(
    file,
    "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0",
  );
  const { app, page } = await launch(root);
  await page.getByRole("button", { name: "Create demo request" }).click();
  await app.evaluate(
    ({ dialog }, path) => {
      dialog.showOpenDialog = async () => ({
        canceled: false,
        filePaths: [path],
      });
    },
    join(root, "deleted.txt"),
  );
  await page.getByRole("button", { name: "Import local evidence" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Evidence could not be read",
  );
  expect(await page.getByRole("alert").innerText()).not.toContain(root);
  await app.evaluate(({ dialog }, path) => {
    dialog.showOpenDialog = async () => ({
      canceled: false,
      filePaths: [path],
    });
  }, file);
  await page.getByRole("button", { name: "Import local evidence" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  await expect(page.getByText(/local-evidence.txt SHA256/)).toBeVisible();
  await page.screenshot({
    path: join(screenshots, "desktop-local-import.png"),
    fullPage: true,
  });
  await app.close();
});
test("real Electron: unavailable Python has visible startup error", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-failure-"));
  const { app, page } = await launch(root, "/missing/python");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
  await page.screenshot({
    path: join(screenshots, "desktop-startup-error.png"),
    fullPage: true,
  });
  await app.close();
});

test("real Electron: unexpected sidecar exit recovers the existing polled run through Retry", async () => {
  const root = await mkdtemp(join(tmpdir(), "audit-exit-"));
  const pidFile = join(root, "python.pid"),
    wrapper = join(root, "python-wrapper.sh");
  await writeFile(
    wrapper,
    `#!/bin/sh\nprintf '%s' "$$" > '${pidFile}'\nexec python3 "$@"\n`,
  );
  await chmod(wrapper, 0o700);
  const { app, page } = await launch(root, wrapper);
  await page.getByRole("button", { name: "Create demo request" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  const run = await page.locator(".agent-footer span").first().textContent();
  const pid = Number(await readFile(pidFile, "utf8"));
  await app.evaluate((_electron, pid) => process.kill(pid, "SIGKILL"), pid);
  await expect(page.getByRole("alert")).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  await expect(page.locator(".agent-footer span").first()).toHaveText(run!);
  await page
    .getByRole("button", { name: "Approve record", exact: true })
    .click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("completed");
  await app.close();
});
