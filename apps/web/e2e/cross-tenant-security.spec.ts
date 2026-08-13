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

test.describe("cross tenant and park security", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("tenant A party not visible to tenant B token", async ({ request }) => {
    const tokenA = await apiLogin(request, ADMIN_USER, ADMIN_PASS, "default");
    const party = await apiJson(request, "post", "/parties", {
      token: tokenA,
      data: { name: uniqueName("OnlyA"), party_type: "ORGANIZATION" },
    });
    expect(party.status).toBe(200);
    const partyId = (party.body as { data: { id: number } }).data.id;

    const tokenB = await apiLogin(request, "admin_b", "adminb123", "tenant_b");
    const getB = await apiJson(request, "get", `/parties/${partyId}`, { token: tokenB });
    expect([404, 403]).toContain(getB.status);

    const listB = await apiJson(request, "get", `/parties?keyword=OnlyA`, { token: tokenB });
    expect(listB.status).toBe(200);
    const items = (listB.body as { data: { items: Array<{ id: number }> } }).data.items;
    expect(items.some((x) => x.id === partyId)).toBeFalsy();
  });

  test("park-scoped limited denial via API", async ({ request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    // limited user has only party:read — lease write must 403
    const limited = await apiLogin(request, "e2e_limited", "limited123");
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("ScopePark"), address: "s" },
    });
    // limited cannot create park
    const denied = await apiJson(request, "post", "/parks", {
      token: limited,
      data: { name: uniqueName("Denied"), address: "x" },
    });
    expect(denied.status).toBe(403);

    // limited cannot create lease
    const leaseDenied = await apiJson(request, "post", "/leases", {
      token: limited,
      data: {
        park_id: (park.body as { data: { id: number } }).data.id,
        party_id: 1,
        start_date: "2026-01-01",
        end_date: "2026-12-31",
      },
    });
    expect([403, 404, 400, 422]).toContain(leaseDenied.status);
    expect(leaseDenied.status).not.toBe(200);
  });

  test("UI limited user cannot reach leases", async ({ page }) => {
    await loginAs(page, "e2e_limited", "limited123");
    await page.goto("/leases");
    await expect(page.getByTestId("forbidden-page")).toBeVisible();
  });
});
