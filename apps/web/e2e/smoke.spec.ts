import { test, expect } from "@playwright/test";

/**
 * 前端路由与登录页烟雾。
 * 完整主链 E2E 需后端可用；此处保证生产构建后的关键路径可打开。
 */
test("login page renders", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /KWZY/i })).toBeVisible();
  await expect(page.getByLabel("用户名")).toBeVisible();
  await expect(page.getByLabel("密码")).toBeVisible();
});

test("unauthenticated redirect to login", async ({ page }) => {
  await page.goto("/workbench");
  await expect(page).toHaveURL(/login/);
});
