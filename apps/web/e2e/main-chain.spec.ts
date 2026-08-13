/**
 * Full browser main chain — no skip when API is down (requireApiHealthy throws).
 */
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

test.describe("browser main chain", () => {
  test("party lease bill payment workbench", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    await requireApiHealthy(request);

    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("MC-Park"), address: "mc" },
    });
    expect(park.status).toBe(200);
    const parkId = (park.body as { data: { id: number } }).data.id;
    const unit = await apiJson(request, "post", "/units", {
      token,
      data: {
        park_id: parkId,
        name: "MC-1",
        code: uniqueName("MCU").slice(0, 16),
        rentable_area: 90,
        status: "VACANT",
      },
    });
    expect(unit.status).toBe(200);
    const unitId = (unit.body as { data: { id: number } }).data.id;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);

    // party
    const partyName = uniqueName("MC-Party");
    await page.goto("/parties");
    await page.getByTestId("party-name").fill(partyName);
    await page.getByTestId("party-create-btn").click();
    await expect(page.getByTestId("party-table")).toContainText(partyName, { timeout: 15000 });
    const parties = await apiJson(request, "get", `/parties?keyword=${encodeURIComponent(partyName)}`, {
      token,
    });
    const partyId = (
      parties.body as { data: { items: Array<{ id: number; name: string }> } }
    ).data.items.find((x) => x.name === partyName)!.id;

    // lease
    await page.goto("/leases");
    await page.getByTestId("lease-park-id").fill(String(parkId));
    await page.getByTestId("lease-party-id").fill(String(partyId));
    await page.getByTestId("lease-unit-id").fill(String(unitId));
    await page.getByTestId("lease-create-btn").click();
    await expect(page.getByTestId("lease-success")).toContainText(/创建/, { timeout: 15000 });
    const row = page.locator("[data-testid^=lease-row-]").first();
    await row.getByRole("button", { name: "提交" }).click();
    await row.getByTestId("lease-activate-btn").click();
    await expect(page.getByTestId("lease-success")).toContainText(/激活/, { timeout: 15000 });

    // bill + pay
    await page.goto("/bills");
    await page.getByTestId("bill-park-id").fill(String(parkId));
    await page.getByTestId("bill-party-id").fill(String(partyId));
    await page.getByTestId("bill-amount").fill("150");
    await page.getByTestId("bill-create-btn").click();
    await expect(page.getByTestId("bill-success")).toBeVisible({ timeout: 15000 });
    const bills = await apiJson(request, "get", "/bills?page=1&page_size=50", { token });
    const billId = (
      bills.body as { data: { items: Array<{ id: number; party_id: number }> } }
    ).data.items.find((b) => b.party_id === partyId)!.id;
    await page.locator(`[data-testid=bill-row-${billId}]`).getByTestId("bill-issue-btn").click();

    await page.goto("/payments");
    await page.getByTestId("pay-park-id").fill(String(parkId));
    await page.getByTestId("pay-party-id").fill(String(partyId));
    await page.getByTestId("pay-bill-id").fill(String(billId));
    await page.getByTestId("pay-amount").fill("150");
    await page.getByTestId("pay-create-btn").click();
    await expect(page.getByTestId("pay-success")).toContainText(/登记/, { timeout: 15000 });

    const billAfter = await apiJson(request, "get", `/bills/${billId}`, { token });
    expect((billAfter.body as { data: { status: string } }).data.status).toBe("PAID");

    await page.goto("/workbench");
    await expect(page.getByTestId("workbench-metrics")).toBeVisible();
    await page.goto("/todos");
    await expect(page.getByTestId("todo-table")).toBeVisible();
    await page.goto("/system");
    await expect(page.getByTestId("system-title")).toBeVisible();
  });
});
