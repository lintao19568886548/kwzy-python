import { test, expect } from "@playwright/test";
import {
  ADMIN_PASS,
  ADMIN_USER,
  LIMITED_PASS,
  LIMITED_USER,
  apiJson,
  apiLogin,
  loginAs,
  requireApiHealthy,
  uniqueName,
} from "./helpers";

test.describe("system admin", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("admin CRUD org user role dict param with secret mask", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/system");
    await expect(page.getByTestId("system-title")).toBeVisible();

    // org
    await page.getByTestId("tab-org").click();
    const orgCode = uniqueName("ORG").slice(0, 16);
    await page.getByTestId("org-code").fill(orgCode);
    await page.getByTestId("org-name").fill(`组织${orgCode}`);
    await page.getByTestId("org-create-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/组织/, { timeout: 15000 });
    await expect(page.getByTestId("org-table")).toContainText(orgCode);

    // users
    await page.getByTestId("tab-users").click();
    const uname = uniqueName("u").replace(/-/g, "").slice(0, 16).toLowerCase();
    await page.getByTestId("user-username").fill(uname);
    await page.getByTestId("user-password").fill("pass1234");
    await page.getByTestId("user-realname").fill("E2E用户");
    await page.getByTestId("user-create-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/用户/, { timeout: 15000 });
    await expect(page.getByTestId("user-table")).toContainText(uname);

    // roles + perms
    await page.getByTestId("tab-roles").click();
    const rcode = uniqueName("R").replace(/-/g, "").slice(0, 12).toUpperCase();
    await page.getByTestId("role-code").fill(rcode);
    await page.getByTestId("role-name").fill(`角色${rcode}`);
    await page.getByTestId("role-perms").fill("party:read,park:read");
    await page.getByTestId("role-create-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/角色/, { timeout: 15000 });
    await expect(page.getByTestId("role-table")).toContainText(rcode);

    // dict
    await page.getByTestId("tab-dict").click();
    const dcode = uniqueName("D").replace(/-/g, "").slice(0, 12).toLowerCase();
    await page.getByTestId("dict-type-code").fill(dcode);
    await page.getByTestId("dict-type-name").fill(`字典${dcode}`);
    await page.getByTestId("dict-type-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/字典类型/, { timeout: 15000 });
    await page.getByTestId("dict-item-label").fill("标签A");
    await page.getByTestId("dict-item-value").fill("VAL_A");
    await page.getByTestId("dict-item-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/字典项/, { timeout: 15000 });
    await expect(page.getByTestId("dict-item-table")).toContainText("标签A");

    // secret param mask
    await page.getByTestId("tab-param").click();
    const pkey = `secret_${uniqueName("k").replace(/-/g, "").slice(0, 10)}`;
    await page.getByTestId("param-key").fill(pkey);
    await page.getByTestId("param-value").fill("super-secret-value-xyz");
    await page.getByTestId("param-secret").check();
    await page.getByTestId("param-save-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/参数/, { timeout: 15000 });
    const row = page.getByTestId(`param-row-${pkey}`);
    await expect(row).toBeVisible({ timeout: 10000 });
    await expect(row.getByTestId("param-value-cell")).toContainText("******");
    await expect(row.getByTestId("param-value-cell")).not.toContainText("super-secret-value-xyz");

    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const params = await apiJson(request, "get", "/system/params", { token });
    expect(params.status).toBe(200);
  });

  test("limited user cannot open system page", async ({ page }) => {
    await loginAs(page, LIMITED_USER, LIMITED_PASS);
    await page.goto("/system");
    await expect(page.getByTestId("forbidden-page")).toBeVisible();
  });
});
