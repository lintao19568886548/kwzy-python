import { test, expect } from "@playwright/test";
import { ADMIN_PASS, ADMIN_USER, loginAs, requireApiHealthy } from "./helpers";

/**
 * Stack smoke — fails if frontend or API not brought up by globalSetup.
 */
test("login page renders", async ({ page, request }) => {
  await requireApiHealthy(request);
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /KWZY/i })).toBeVisible();
  await expect(page.getByLabel("用户名")).toBeVisible();
  await expect(page.getByLabel("密码")).toBeVisible();
});

test("unauthenticated redirect to login", async ({ page, request }) => {
  await requireApiHealthy(request);
  await page.goto("/workbench");
  await expect(page).toHaveURL(/login/);
});

test("frontend root responds", async ({ page, request }) => {
  await requireApiHealthy(request);
  const res = await page.goto("/");
  expect(res?.ok() || res?.status() === 304 || page.url().includes("login")).toBeTruthy();
});

test("primary navigation resets stale page scroll", async ({ page, request }) => {
  await requireApiHealthy(request);
  await loginAs(page, ADMIN_USER, ADMIN_PASS);
  await page.goto("/workbench");
  await expect(page.getByTestId("workbench-title")).toBeVisible();
  await expect(page.getByTestId("widget-operations_metrics")).toBeVisible();
  await page.evaluate(() => {
    document.body.style.minHeight = "2000px";
  });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  await page.getByRole("link", { name: "合同", exact: true }).click();
  await expect(page).toHaveURL(/\/leases$/);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByTestId("leases-title")).toBeVisible();
});
