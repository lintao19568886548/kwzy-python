import { test, expect } from "@playwright/test";
import { requireApiHealthy } from "./helpers";

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
