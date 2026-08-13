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

test.describe("lease lifecycle", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create submit activate lease via UI", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const parkName = uniqueName("LeasePark");
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: parkName, address: "lease-road" },
    });
    expect(park.status).toBe(200);
    const parkId = (park.body as { data: { id: number } }).data.id;
    const unit = await apiJson(request, "post", "/units", {
      token,
      data: {
        park_id: parkId,
        name: "L-101",
        code: uniqueName("U").slice(0, 20),
        rentable_area: 120,
        status: "VACANT",
      },
    });
    expect(unit.status).toBe(200);
    const unitId = (unit.body as { data: { id: number } }).data.id;
    const party = await apiJson(request, "post", "/parties", {
      token,
      data: { name: uniqueName("LeaseParty"), party_type: "ORGANIZATION" },
    });
    const partyId = (party.body as { data: { id: number } }).data.id;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leases");
    await page.getByTestId("lease-park-id").fill(String(parkId));
    await page.getByTestId("lease-party-id").fill(String(partyId));
    await page.getByTestId("lease-unit-id").fill(String(unitId));
    await page.getByTestId("lease-start").fill("2026-01-01");
    await page.getByTestId("lease-end").fill("2026-12-31");
    await page.getByTestId("lease-area").fill("80");
    await page.getByTestId("lease-deposit").fill("5000");
    await page.getByTestId("lease-create-btn").click();
    await expect(page.getByTestId("lease-success")).toContainText(/创建/, { timeout: 15000 });

    // submit then activate first DRAFT row
    const firstRow = page.locator("[data-testid^=lease-row-]").first();
    await expect(firstRow).toBeVisible();
    await firstRow.getByRole("button", { name: "提交" }).click();
    await expect(page.getByTestId("lease-success")).toContainText(/提交/, { timeout: 15000 });
    await firstRow.getByTestId("lease-activate-btn").click();
    await expect(page.getByTestId("lease-success")).toContainText(/激活/, { timeout: 15000 });

    const listed = await apiJson(request, "get", "/leases?page=1&page_size=50", { token });
    expect(listed.status).toBe(200);
    const items = (listed.body as { data: { items: Array<{ status: string; party_id: number }> } })
      .data.items;
    expect(items.some((x) => x.party_id === partyId && x.status === "ACTIVE")).toBeTruthy();
  });
});
