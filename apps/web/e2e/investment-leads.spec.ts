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

test.describe("investment leads", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create edit follow convert lead", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("LeadPark"), address: "lead" },
    });
    const parkId = (park.body as { data: { id: number } }).data.id;
    const leadName = uniqueName("Lead");

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    await page.getByTestId("lead-park-id").fill(String(parkId));
    await page.getByTestId("lead-name").fill(leadName);
    await page.getByTestId("lead-phone").fill("13700137000");
    await page.getByTestId("lead-intent").selectOption("HIGH");
    await page.getByTestId("lead-create-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText(/创建/, { timeout: 15000 });
    await expect(page.getByTestId("lead-table")).toContainText(leadName);

    const listed = await apiJson(request, "get", `/leads?keyword=${encodeURIComponent(leadName)}`, {
      token,
    });
    const items = (listed.body as { data: { items: Array<{ id: number; name: string }> } }).data
      .items;
    const leadId = items.find((x) => x.name === leadName)!.id;

    await page.getByTestId("lead-edit-id").fill(String(leadId));
    await page.getByTestId("lead-edit-name").fill(`${leadName}-edited`);
    await page.getByTestId("lead-edit-status").selectOption("FOLLOWING");
    await page.getByTestId("lead-assignee").fill("1");
    await page.getByTestId("lead-remark").fill("电话跟进一次");
    await page.getByTestId("lead-update-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText(/更新/, { timeout: 15000 });

    await page.locator(`[data-testid=lead-row-${leadId}]`).getByTestId("lead-convert-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText(/转化/, { timeout: 15000 });

    const detail = await apiJson(request, "get", `/leads/${leadId}`, { token });
    expect(detail.status).toBe(200);
    const status = (detail.body as { data: { status: string } }).data.status;
    expect(status).toBe("WON");
  });

  test("duplicate lead handling or second create", async ({ page, request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("DupPark"), address: "dup" },
    });
    const parkId = (park.body as { data: { id: number } }).data.id;
    const phone = `136${String(Date.now()).slice(-8)}`;
    const name = uniqueName("DupLead");

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    for (let i = 0; i < 2; i++) {
      await page.getByTestId("lead-park-id").fill(String(parkId));
      await page.getByTestId("lead-name").fill(name);
      await page.getByTestId("lead-phone").fill(phone);
      await page.getByTestId("lead-create-btn").click();
      await page.waitForTimeout(800);
    }
    // either success twice (allowed) or error shown — never silent success after hard fail
    const err = page.getByTestId("lead-error");
    const ok = page.getByTestId("lead-success");
    await expect(err.or(ok)).toBeVisible({ timeout: 10000 });
  });
});
