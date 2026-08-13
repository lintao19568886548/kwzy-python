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
    expect(await page.evaluate(() => localStorage.getItem("kwzy_refresh_token"))).toBeNull();
    const refreshCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === "kwzy_refresh"
    );
    expect(refreshCookie?.httpOnly).toBe(true);
    expect(refreshCookie?.sameSite).toBe("Strict");
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
    await page.getByTestId(`user-revoke-${uname}`).click();
    await expect(page.getByTestId("system-success")).toContainText(/会话/, { timeout: 15000 });
    await page.getByTestId(`user-status-${uname}`).click();
    await expect(page.getByTestId(`user-row-${uname}`)).toContainText("DISABLED", {
      timeout: 15000,
    });

    // roles + perms
    await page.getByTestId("tab-roles").click();
    const rcode = uniqueName("R").replace(/-/g, "").slice(0, 12).toUpperCase();
    await page.getByTestId("role-code").fill(rcode);
    await page.getByTestId("role-name").fill(`角色${rcode}`);
    await page.getByTestId("role-perms").selectOption(["party:read", "park:read"]);
    await page.getByTestId("role-create-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/角色/, { timeout: 15000 });
    await expect(page.getByTestId("role-table")).toContainText(rcode);
    await page.getByTestId(`role-edit-${rcode}`).click();
    await page.getByTestId("role-scope-mode").selectOption("ALL");
    await page.getByTestId("role-create-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/角色授权/, {
      timeout: 15000,
    });
    await page.getByTestId(`role-disable-${rcode}`).click();
    await expect(page.getByTestId(`role-row-${rcode}`)).toContainText("DISABLED", {
      timeout: 15000,
    });

    // menu lifecycle
    await page.getByTestId("tab-menus").click();
    const menuName = uniqueName("菜单").slice(0, 20);
    await page.getByTestId("menu-name").fill(menuName);
    await page.getByTestId("menu-path").fill(`/e2e-${rcode.toLowerCase()}`);
    await page.getByTestId("menu-permission").selectOption("park:read");
    await page.getByTestId("menu-save-btn").click();
    await expect(page.getByTestId("system-success")).toContainText(/菜单/, { timeout: 15000 });
    let menuRow = page.getByRole("row").filter({ hasText: menuName });
    await expect(menuRow).toBeVisible();
    await menuRow.getByRole("button", { name: "编辑" }).click();
    await page.getByTestId("menu-name").fill(`${menuName}-更新`);
    await page.getByTestId("menu-save-btn").click();
    menuRow = page.getByRole("row").filter({ hasText: `${menuName}-更新` });
    await expect(menuRow).toBeVisible({ timeout: 15000 });
    await menuRow.getByRole("button", { name: "停用" }).click();
    await expect(menuRow).toContainText("DISABLED", { timeout: 15000 });

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

  test("system admin remains keyboard reachable at tablet width", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/system");
    await expect(page.getByRole("navigation", { name: "系统管理分类" })).toBeVisible();
    await page.getByTestId("tab-org").focus();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("tab-users")).toBeFocused();
    await page.getByTestId("tab-roles").click();
    await expect(page.getByTestId("role-scope-mode")).toBeVisible();
    await expect(page.getByTestId("role-perms")).toBeVisible();
  });
});
