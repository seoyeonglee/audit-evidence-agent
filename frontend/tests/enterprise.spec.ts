import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
mkdirSync("../docs/screenshots", { recursive: true });

test("graph interruption, exact sources, independent approval and final report", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Agent Runtime", exact: true })
    .click();
  await page.getByRole("button", { name: "Create demo request" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  await expect(
    page.getByText("production-admin", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/agent-waiting-review.png",
    fullPage: true,
  });
  await page
    .getByLabel("Reviewer feedback")
    .fill("Verified source spans, period and complete access population.");
  await page
    .getByRole("button", { name: "Approve record", exact: true })
    .click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("completed");
  await expect(
    page
      .getByText(
        "Verified source spans, period and complete access population.",
        { exact: true },
      )
      .first(),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/agent-approved.png",
    fullPage: true,
  });
  await expect(
    page.getByRole("button", { name: "Export report" }),
  ).toBeEnabled();
});

test("conflicting evidence blocks approval and retains reviewer feedback", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Agent Runtime", exact: true })
    .click();
  await page.getByLabel("Demo scenario").selectOption("conflict");
  await page.getByRole("button", { name: "Create demo request" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  await expect(
    page.getByRole("button", { name: "Approve record", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Reviewer feedback")
    .fill("Resolve the conflicting reviewed user counts: 84 versus 91.");
  await page
    .getByRole("button", { name: "Request changes", exact: true })
    .click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("completed");
  await page.screenshot({
    path: "../docs/screenshots/agent-needs-changes.png",
    fullPage: true,
  });
});

test("changed source version blocks stale approval and offers a new run", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Agent Runtime", exact: true })
    .click();
  await page.getByRole("button", { name: "Create demo request" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  const rid = await page.getByLabel("Evidence request").inputValue();
  const session = await (
    await request.post("http://localhost:8000/api/v2/demo/session", {
      data: { persona: "owner" },
    })
  ).json();
  const intake = await request.post(
    `http://localhost:8000/api/v2/requests/${rid}/documents`,
    {
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Idempotency-Key": crypto.randomUUID(),
      },
      data: {
        filename: "updated.txt",
        media_type: "text/plain",
        content:
          "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 91\nexceptions: 0",
      },
    },
  );
  expect(intake.status()).toBe(202);
  await expect(
    page.getByText(
      "Snapshot changed. Start a new run for the current evidence.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve record", exact: true }),
  ).toBeDisabled();
  await page.screenshot({
    path: "../docs/screenshots/agent-blocked-stale.png",
    fullPage: true,
  });
});

test("API interruption is visible and retry restores the workspace at mobile width", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v2/demo/session", (r) => r.abort());
  await page.goto("/");
  await page
    .getByRole("button", { name: "Agent Runtime", exact: true })
    .click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.unroute("**/api/v2/demo/session");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "Create demo request" }).click();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../docs/screenshots/agent-mobile.png",
    fullPage: true,
  });
  await page.getByLabel("Session persona").selectOption("owner");
  await expect(
    page.getByRole("button", { name: "Create demo request" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Approve record", exact: true }),
  ).toBeDisabled();
});

test("completed report can be reopened after navigating to another request", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Agent Runtime", exact: true })
    .click();
  await page.getByRole("button", { name: "Create demo request" }).click();
  await expect(page.getByLabel("Evidence request")).toHaveValue(/^AGENT-/);
  const first = await page.getByLabel("Evidence request").inputValue();
  await page.getByRole("button", { name: "Start agent run" }).click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("waiting_review");
  await page
    .getByRole("button", { name: "Approve record", exact: true })
    .click();
  await page.getByRole("button", { name: "Execute graph" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("completed");
  await page.getByRole("button", { name: "Create demo request" }).click();
  await expect(page.getByLabel("Evidence request")).not.toHaveValue(first);
  await page.getByLabel("Evidence request").selectOption(first);
  await expect(page.getByTestId("run-status")).toHaveText("completed");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export report" }).click();
  expect((await download).suggestedFilename()).toMatch(/^audit-.*\.json$/);
  await page.reload();
  await page
    .getByRole("button", { name: "Agent Runtime", exact: true })
    .click();
  await expect(page.getByTestId("run-status")).toHaveText("completed");
});
