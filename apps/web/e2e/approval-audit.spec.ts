import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  ADMIN_PASS,
  ADMIN_USER,
  apiJson,
  apiLogin,
  loginAs,
  requireApiHealthy,
  uniqueName,
} from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EVIDENCE_DIR = path.resolve(
  __dirname,
  "../../../docs/06-implementation/evidence/platform-approval-audit-center"
);

type Envelope<T> = { data: T };

function dataOf<T>(body: unknown): T {
  return (body as Envelope<T>).data;
}

async function createRoleAndUser(
  request: APIRequestContext,
  token: string,
  prefix: string,
  permissions: string[]
) {
  const suffix = uniqueName(prefix).replace(/-/g, "").slice(-11).toLowerCase();
  const role = dataOf<{ id: number }>((await apiJson(request, "post", "/system/roles", {
    token,
    data: {
      code: (prefix + "_" + suffix).slice(0, 32).toUpperCase(),
      name: prefix + "审批角色" + suffix,
      permission_codes: permissions,
      park_ids: [],
      all_parks: true,
    },
  })).body);
  const username = (prefix.toLowerCase() + suffix).slice(0, 28);
  const password = "Approval-E2E!2026";
  const response = await apiJson(request, "post", "/system/users", {
    token,
    data: {
      username,
      password,
      real_name: prefix + "审批用户" + suffix,
      phone: "13800138000",
      role_ids: [role.id],
      park_ids: [],
      all_parks: true,
    },
  });
  expect(response.status).toBe(200);
  return { ...dataOf<{ id: number }>(response.body), username, password };
}

test.describe("platform approval and audit center", () => {
  test.beforeAll(() => fs.mkdirSync(EVIDENCE_DIR, { recursive: true }));
  test.beforeEach(async ({ request }) => requireApiHealthy(request));

  test("real HTTP and browser complete definition, delegation, approval and audit journey", async ({
    page,
    request,
  }) => {
    const adminToken = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const original = await createRoleAndUser(request, adminToken, "ORIGINAL", [
      "approval.task.read",
      "approval.task.decide",
      "approval.delegation.manage",
    ]);
    const delegate = await createRoleAndUser(request, adminToken, "DELEGATE", [
      "approval.task.read",
      "approval.task.decide",
    ]);

    await loginAs(page, original.username, original.password);
    await page.goto("/approvals");
    await page.getByTestId("tab-delegations").click();
    await page.getByTestId("delegation-create-open").click();
    await page.getByTestId("delegation-user").fill(String(delegate.id));
    const now = new Date();
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    const localValue = (value: Date) => {
      const shifted = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
      return shifted.toISOString().slice(0, 16);
    };
    await page.getByTestId("delegation-start").fill(localValue(new Date(now.getTime() - 60_000)));
    await page.getByTestId("delegation-end").fill(localValue(tomorrow));
    await page.getByTestId("delegation-submit").click();
    await expect(page.getByTestId("approval-success")).toContainText("委托已生效");

    const code = ("FLOW" + uniqueName("").replace(/-/g, "")).slice(0, 28).toUpperCase();
    const businessId = uniqueName("PURCHASE");
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/approvals");
    await page.getByTestId("tab-definitions").click();
    await page.getByTestId("definition-create-open").click();
    await page.getByTestId("definition-code").fill(code);
    await page.getByTestId("definition-name").fill("采购付款分级审批");
    await page.locator("[data-testid='definition-form'] .assignee input").first().fill(String(original.id));
    await page.getByTestId("definition-submit").click();
    await expect(page.getByTestId("approval-success")).toContainText("草稿已保存");
    const definitionCard = page.locator(".definition-card", { hasText: code });
    await expect(definitionCard).toBeVisible();
    await definitionCard.getByRole("button", { name: "发布草稿" }).click();
    await expect(page.getByTestId("approval-success")).toContainText("已发布");
    await definitionCard.getByRole("button", { name: "查看/编辑" }).click();
    await expect(page.getByTestId("definition-published-readonly")).toBeVisible();
    await expect(page.getByTestId("definition-submit")).toHaveCount(0);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-published-definition-readonly.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "关闭" }).click();

    await page.getByTestId("tab-applications").click();
    await page.getByTestId("approval-create-open").click();
    await page.getByTestId("approval-definition-code").fill(code);
    await page.getByTestId("approval-biz-id").fill(businessId);
    await page.getByTestId("approval-title").fill("供应商首付款审批");
    await page.getByTestId("approval-create-submit").click();
    await expect(page.getByTestId("approval-success")).toContainText("已提交");
    await expect(page.getByTestId("approvals-table")).toContainText(businessId);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-approval-applications.png"),
      fullPage: true,
    });

    await loginAs(page, delegate.username, delegate.password);
    await page.goto("/approvals");
    await page.getByTestId("tab-tasks").click();
    const taskCard = page.locator(".task-card", { hasText: businessId });
    await expect(taskCard).toBeVisible();
    await taskCard.getByRole("button", { name: "处理待办" }).click();
    await page.getByTestId("task-remark").fill("受托核验通过");
    let conflicted = false;
    await page.route("**/approval-tasks/*/decide", async (route) => {
      if (!conflicted) {
        conflicted = true;
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({ code: "VERSION_CONFLICT", message: "并发版本冲突", data: null }),
        });
        return;
      }
      await route.continue();
    });
    await page.getByTestId("task-decision-submit").click();
    await expect(page.getByTestId("approval-error")).toContainText("表单内容已保留");
    await expect(page.getByTestId("task-remark")).toHaveValue("受托核验通过");
    await page.getByTestId("task-decision-submit").click();
    await expect(page.getByTestId("approval-success")).toContainText("决定已提交");
    await expect(taskCard).toHaveCount(0);
    await page.getByTestId("task-processed-filter").selectOption("true");
    await expect(page.locator(".task-card", { hasText: businessId })).toBeVisible();

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/approvals");
    await page.getByTestId("tab-audit").click();
    await page.getByTestId("audit-action-filter").fill("decision");
    await page.locator("[data-testid='audit-filters'] button[type='submit']").click();
    await expect(page.getByTestId("audit-table")).toContainText("decision");
    await page.getByTestId("audit-verify").click();
    await expect(page.getByTestId("audit-verification")).toContainText("VERIFIED");
    await expect(page.getByTestId("audit-verification")).toContainText("失败 0");
    const download = page.waitForEvent("download");
    await page.getByTestId("audit-export").click();
    expect((await download).suggestedFilename()).toBe("audit-logs.csv");
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-audit-integrity.png"),
      fullPage: true,
    });
  });

  test("read-only role sees governed data and fabricated write is forbidden", async ({
    page,
    request,
  }) => {
    const adminToken = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const viewer = await createRoleAndUser(request, adminToken, "AUDITVIEW", [
      "approval.definition.read",
      "audit.read",
    ]);
    const viewerToken = await apiLogin(request, viewer.username, viewer.password);
    const denied = await apiJson(request, "post", "/approval-definitions", {
      token: viewerToken,
      headers: { "X-Permissions": "approval.definition.write" },
      data: { code: "FORGED_WRITE", name: "越权定义", biz_type: "PURCHASE", steps: [] },
    });
    expect(denied.status).toBe(403);

    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, viewer.username, viewer.password);
    await page.goto("/approvals");
    await expect(page.getByTestId("approval-center-title")).toBeVisible();
    await expect(page.getByTestId("tab-applications")).toHaveCount(0);
    await page.getByTestId("tab-definitions").click();
    await expect(page.getByTestId("definitions-readonly")).toBeVisible();
    await expect(page.getByTestId("definition-create-open")).toHaveCount(0);
    await page.getByTestId("tab-audit").click();
    await expect(page.getByTestId("audit-panel")).toBeVisible();
    await expect(page.getByTestId("approval-loading")).toHaveCount(0);
    await expect(page.getByTestId("audit-export")).toHaveCount(0);
    expect(await page.evaluate(() => document.body.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-tablet-approval-audit-readonly.png"),
      fullPage: true,
    });
  });

  test("mobile network failure preserves a recoverable retry state without overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    let failed = false;
    await page.route("**/api/v1/approvals?*", async (route) => {
      if (!failed) {
        failed = true;
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ code: "DEPENDENCY_UNAVAILABLE", message: "审批服务暂不可用", data: null }),
        });
        return;
      }
      await route.continue();
    });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/approvals");
    await expect(page.getByTestId("approval-error")).toBeVisible();
    await page.getByTestId("approval-retry").click();
    await expect(page.getByTestId("approval-error")).toHaveCount(0);
    await expect(page.getByTestId("applications-panel")).toBeVisible();
    expect(await page.evaluate(() => document.body.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-mobile-approval-retry.png"),
      fullPage: true,
    });
  });
});
