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

test.describe("party lifecycle", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create party and contact via UI", async ({ page, request }) => {
    const name = uniqueName("Party");
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/parties");
    await expect(page.getByTestId("parties-title")).toBeVisible();

    await page.getByTestId("party-name").fill(name);
    await page.getByTestId("party-type").selectOption("ORGANIZATION");
    await page.getByTestId("party-phone").fill("13800138000");
    await page.getByTestId("party-create-btn").click();

    await expect(page.getByTestId("party-success")).toContainText(/已创建/, { timeout: 15000 });
    await expect(page.getByTestId("party-table")).toContainText(name);

    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const listed = await apiJson(request, "get", `/parties?keyword=${encodeURIComponent(name)}`, {
      token,
    });
    expect(listed.status).toBe(200);
    const items = (listed.body as { data: { items: Array<{ id: number; name: string }> } }).data
      .items;
    expect(items.some((x) => x.name === name)).toBeTruthy();
    const partyId = items.find((x) => x.name === name)!.id;

    await page.getByTestId("contact-party-id").fill(String(partyId));
    await page.getByTestId("contact-name").fill("联系人甲");
    await page.getByTestId("contact-phone").fill("13900139000");
    await page.getByTestId("contact-create-btn").click();
    await expect(page.getByTestId("party-success")).toContainText(/联系人/, { timeout: 15000 });

    const contacts = await apiJson(request, "get", `/parties/${partyId}/contacts`, { token });
    expect(contacts.status).toBe(200);
  });

  test("empty name validation", async ({ page }) => {
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/parties");
    // HTML required attribute should block empty submit
    await page.getByTestId("party-create-btn").click();
    await expect(page.getByTestId("party-name")).toBeFocused();
  });
});
