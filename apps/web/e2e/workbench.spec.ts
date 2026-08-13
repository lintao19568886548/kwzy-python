import { test, expect } from "@playwright/test";
import {
  ADMIN_PASS,
  ADMIN_USER,
  apiJson,
  apiLogin,
  loginAs,
  requireApiHealthy,
  uniqueName,
} from "./helpers";

test.describe("workbench & todos", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("metrics and todo complete cancel reopen jump", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);

    // create a manual work item if API allows
    const created = await apiJson(request, "post", "/work-items", {
      token,
      data: {
        title: uniqueName("Todo"),
        item_type: "MANUAL",
        priority: "MEDIUM",
        source_type: "MANUAL",
        source_id: String(Date.now()),
      },
    });
    // if manual create not allowed, seed via bill issue
    if (created.status >= 400) {
      const park = await apiJson(request, "post", "/parks", {
        token,
        data: { name: uniqueName("WbPark"), address: "wb" },
      });
      const parkId = (park.body as { data: { id: number } }).data.id;
      const party = await apiJson(request, "post", "/parties", {
        token,
        data: { name: uniqueName("WbParty"), party_type: "ORGANIZATION" },
      });
      const partyId = (party.body as { data: { id: number } }).data.id;
      const bill = await apiJson(request, "post", "/bills", {
        token,
        data: {
          park_id: parkId,
          party_id: partyId,
          period_start: "2026-01-01",
          period_end: "2026-01-31",
          lines: [{ fee_code: "RENT", quantity: "1", unit_price: "50" }],
        },
      });
      const billId = (bill.body as { data: { id: number } }).data.id;
      await apiJson(request, "post", `/bills/${billId}/issue`, { token });
    }

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/workbench");
    await expect(page.getByTestId("workbench-title")).toBeVisible();
    await expect(page.getByTestId("workbench-metrics")).toBeVisible();
    await expect(page.getByTestId("metric-open-todos")).toBeVisible();

    await page.goto("/todos");
    await expect(page.getByTestId("todos-title")).toBeVisible();
    const row = page.locator("[data-testid^=todo-row-]").first();
    await expect(row).toBeVisible({ timeout: 20000 });

    await row.getByTestId("todo-jump-btn").click();
    // jumped to a business page
    await expect(page).not.toHaveURL(/login/);

    await page.goto("/todos");
    const openRow = page.locator("[data-testid^=todo-row-]").first();
    if (await openRow.getByTestId("todo-complete-btn").count()) {
      await openRow.getByTestId("todo-complete-btn").click();
      await expect(page.getByTestId("todo-success")).toContainText(/完成/, { timeout: 15000 });
    }

    await page.getByTestId("todo-status-filter").selectOption("DONE");
    await page.getByTestId("todo-refresh").click();
    const doneRow = page.locator("[data-testid^=todo-row-]").first();
    if (await doneRow.getByTestId("todo-reopen-btn").count()) {
      await doneRow.getByTestId("todo-reopen-btn").click();
      await expect(page.getByTestId("todo-success")).toContainText(/重新打开|重开/, {
        timeout: 15000,
      });
    }

    await page.getByTestId("todo-status-filter").selectOption("OPEN");
    await page.getByTestId("todo-refresh").click();
    const cancelRow = page.locator("[data-testid^=todo-row-]").first();
    if (await cancelRow.getByTestId("todo-cancel-btn").count()) {
      await cancelRow.getByTestId("todo-cancel-btn").click();
      await expect(page.getByTestId("todo-success")).toContainText(/取消/, { timeout: 15000 });
    }
  });
});
