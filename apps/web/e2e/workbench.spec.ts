import { test, expect } from "@playwright/test";
import {
  ADMIN_PASS,
  ADMIN_USER,
  apiJson,
  apiLogin,
  LIMITED_PASS,
  LIMITED_USER,
  loginAs,
  requireApiHealthy,
  uniqueName,
  WORKBENCH_VIEWER_PASS,
  WORKBENCH_VIEWER_USER,
} from "./helpers";

test.describe("workbench & todos", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("metrics and todo complete cancel reopen jump", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);

    // create a manual work item if API allows
    const created = await apiJson(request, "post", "/work-items", {
      token,
      data: {
        title: uniqueName("Todo"),
        item_type: "MANUAL",
        priority: "MEDIUM",
        source_type: "MANUAL",
        source_id: String(Date.now()),
      },
    });
    // if manual create not allowed, seed via bill issue
    if (created.status >= 400) {
      const park = await apiJson(request, "post", "/parks", {
        token,
        data: { name: uniqueName("WbPark"), address: "wb" },
      });
      const parkId = (park.body as { data: { id: number } }).data.id;
      const party = await apiJson(request, "post", "/parties", {
        token,
        data: { name: uniqueName("WbParty"), party_type: "ORGANIZATION" },
      });
      const partyId = (party.body as { data: { id: number } }).data.id;
      const bill = await apiJson(request, "post", "/bills", {
        token,
        data: {
          park_id: parkId,
          party_id: partyId,
          period_start: "2026-01-01",
          period_end: "2026-01-31",
          lines: [{ fee_code: "RENT", quantity: "1", unit_price: "50" }],
        },
      });
      const billId = (bill.body as { data: { id: number } }).data.id;
      await apiJson(request, "post", `/bills/${billId}/issue`, { token });
    }

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/workbench");
    await expect(page.getByTestId("workbench-title")).toBeVisible();
    await expect(page.getByTestId("workbench-metrics")).toBeVisible();
    await expect(page.getByTestId("metric-open-todos")).toBeVisible();

    await page.goto("/todos");
    await expect(page.getByTestId("todos-title")).toBeVisible();
    const row = page.locator("[data-testid^=todo-row-]").first();
    await expect(row).toBeVisible({ timeout: 20000 });

    await row.getByTestId("todo-jump-btn").click();
    // jumped to a business page
    await expect(page).not.toHaveURL(/login/);

    await page.goto("/todos");
    const openRow = page.locator("[data-testid^=todo-row-]").first();
    if (await openRow.getByTestId("todo-complete-btn").count()) {
      await openRow.getByTestId("todo-complete-btn").click();
      await expect(page.getByTestId("todo-success")).toContainText(/完成/, { timeout: 15000 });
    }

    await page.getByTestId("todo-status-filter").selectOption("DONE");
    await page.getByTestId("todo-refresh").click();
    const doneRow = page.locator("[data-testid^=todo-row-]").first();
    if (await doneRow.getByTestId("todo-reopen-btn").count()) {
      await doneRow.getByTestId("todo-reopen-btn").click();
      await expect(page.getByTestId("todo-success")).toContainText(/重新打开|重开/, {
        timeout: 15000,
      });
    }

    await page.getByTestId("todo-status-filter").selectOption("OPEN");
    await page.getByTestId("todo-refresh").click();
    const cancelRow = page.locator("[data-testid^=todo-row-]").first();
    if (await cancelRow.getByTestId("todo-cancel-btn").count()) {
      await cancelRow.getByTestId("todo-cancel-btn").click();
      await expect(page.getByTestId("todo-success")).toContainText(/取消/, { timeout: 15000 });
    }
  });

  test("live notification automation and personal layout round trip", async ({ page, request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const me = await apiJson(request, "get", "/auth/me", { token });
    expect(me.status).toBe(200);
    const userId = Number((me.body as { data: { id: number } }).data.id);
    const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
    const title = `自动化消息-${suffix}`;
    const created = await apiJson(request, "post", "/automation-rules", {
      token,
      data: {
        code: `UI_NOTIFICATION_${suffix}`,
        name: `UI 通知规则 ${suffix}`,
        event_type: "TEST_AUTOMATION_EVENT",
        conditions: [{ field: "status", operator: "EQ", value: "READY" }],
        actions: [
          {
            type: "CREATE_NOTIFICATION",
            title,
            content: "浏览器验收消息",
            recipient_user_id: userId,
            category: "E2E",
            deep_link: "/workbench",
          },
        ],
      },
    });
    expect(created.status).toBe(200);
    const rule = (created.body as { data: { id: number; lock_version: number } }).data;
    const published = await apiJson(request, "post", `/automation-rules/${rule.id}/publish`, {
      token,
      data: { expected_version: rule.lock_version },
    });
    expect(published.status).toBe(200);
    const emitted = await apiJson(request, "post", "/business-events", {
      token,
      data: {
        event_type: "TEST_AUTOMATION_EVENT",
        source_type: "E2E",
        source_id: suffix,
        idempotency_key: `e2e-notification:${suffix}`,
        payload: { title, description: "浏览器验收", status: "READY", deep_link: "/workbench" },
      },
    });
    expect(emitted.status).toBe(200);
    const dispatched = await apiJson(request, "post", "/business-events/dispatch", { token });
    expect(dispatched.status).toBe(200);

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/workbench");
    await expect(page.getByTestId("widget-operations_metrics")).toBeVisible();
    await page.getByTestId("workbench-tab-notifications").click();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    const message = page.locator("article[data-testid^=notification-]", { hasText: title });
    await message.getByRole("button", { name: "已读" }).click();
    await expect(message.getByRole("button", { name: "已读" })).toHaveCount(0);

    await page.getByTestId("workbench-tab-dashboard").click();
    await page.getByTestId("layout-edit").click();
    await expect(page.getByTestId("layout-drawer")).toBeVisible();
    await page.getByTestId("layout-save").click();
    await expect(page.getByTestId("workbench-success")).toContainText("布局已保存");
    await page.getByTestId("layout-edit").click();
    await page.getByTestId("layout-reset").click();
    await expect(page.getByTestId("workbench-success")).toContainText("默认布局");

    await page.getByTestId("workbench-tab-automation").click();
    await expect(page.getByTestId("automation-ops")).toContainText(`UI 通知规则 ${suffix}`);
    await expect(page.getByTestId("automation-ops")).toContainText("TEST_AUTOMATION_EVENT");
  });

  test("read-only role stays scoped and responsive while forbidden role gets 403 UX", async ({ page }, testInfo) => {
    await loginAs(page, LIMITED_USER, LIMITED_PASS);
    await page.goto("/workbench");
    await expect(page).toHaveURL(/\/forbidden/);
    await expect(page.getByTestId("denied-banner")).toBeVisible();

    await loginAs(page, WORKBENCH_VIEWER_USER, WORKBENCH_VIEWER_PASS);
    for (const viewport of [
      { width: 1440, height: 900, name: "desktop" },
      { width: 820, height: 1080, name: "tablet" },
      { width: 390, height: 844, name: "mobile" },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/workbench");
      await expect(page.getByTestId("widget-operations_metrics")).toBeVisible();
      await expect(page.getByTestId("layout-edit")).toHaveCount(0);
      await expect(page.getByTestId("workbench-tab-notifications")).toBeVisible();
      await expect(page.getByTestId("workbench-tab-automation")).toHaveCount(0);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      ).toBeTruthy();
      await testInfo.attach(`workbench-readonly-${viewport.name}`, {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    }
  });

  test("offline retry and optimistic layout conflict remain actionable", async ({ page, request }) => {
    const abort = (route: import("@playwright/test").Route) => route.abort("failed");
    await page.route("**/workbench/layout", abort);
    await page.route("**/workbench/summary", abort);
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/workbench");
    await expect(page.getByTestId("workbench-error")).toContainText("工作台暂时不可用");
    await page.unroute("**/workbench/layout", abort);
    await page.unroute("**/workbench/summary", abort);
    await page.getByRole("button", { name: "重试" }).click();
    await expect(page.getByTestId("widget-operations_metrics")).toBeVisible();

    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const current = await apiJson(request, "get", "/workbench/layout", { token });
    expect(current.status).toBe(200);
    const layout = (current.body as { data: { source: string; lock_version: number; widgets: Array<Record<string, unknown>> } }).data;
    const widgets = layout.widgets.map((widget) => ({
      widget_key: widget.widget_key,
      position_x: widget.position_x,
      position_y: widget.position_y,
      width: widget.width,
      height: widget.height,
      visible: widget.visible,
      config: widget.config,
    }));
    await page.getByTestId("layout-edit").click();
    const competing = await apiJson(request, "put", "/workbench/layout", {
      token,
      data: {
        expected_version: layout.source === "USER" ? layout.lock_version : 0,
        name: `并发窗口-${Date.now()}`,
        widgets,
      },
    });
    expect(competing.status).toBe(200);
    await page.getByTestId("layout-save").click();
    await expect(page.getByTestId("workbench-error")).toContainText("布局版本冲突");
    const cleanup = await apiJson(request, "delete", "/workbench/layout", { token });
    expect(cleanup.status).toBe(200);
  });

  test("admin controls edit drafts, toggle schedules, and save role defaults", async ({ page, request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
    const ruleResponse = await apiJson(request, "post", "/automation-rules", {
      token,
      data: {
        code: `UI_DRAFT_${suffix}`,
        name: `UI 草稿 ${suffix}`,
        event_type: "TEST_AUTOMATION_EVENT",
        actions: [
          {
            type: "CREATE_WORK_ITEM",
            title: "处理 ${payload.title}",
            item_type: "UI_DRAFT",
            assignee_user_id: 1,
            deep_link: "/todos",
          },
        ],
      },
    });
    expect(ruleResponse.status).toBe(200);
    const rule = (ruleResponse.body as { data: { id: number } }).data;
    const scheduleResponse = await apiJson(request, "post", "/scheduler/definitions", {
      token,
      data: {
        code: `UI_SCHEDULE_${suffix}`,
        name: `UI 调度 ${suffix}`,
        handler_key: "OUTBOX_DISPATCH",
        parameters: { limit: 10 },
        cadence_seconds: 60,
        enabled: false,
      },
    });
    expect(scheduleResponse.status).toBe(200);
    const schedule = (scheduleResponse.body as { data: { id: number } }).data;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/workbench");
    await page.getByTestId("workbench-tab-automation").click();
    const ruleCard = page.getByTestId(`automation-rule-${rule.id}`);
    await ruleCard.getByRole("button", { name: "编辑草稿" }).click();
    await expect(page.getByTestId("rule-draft-drawer")).toBeVisible();
    await page.getByTestId("rule-draft-drawer").getByLabel("规则名称").fill(`UI 草稿已编辑 ${suffix}`);
    await page.getByTestId("rule-draft-drawer").getByRole("button", { name: "保存草稿" }).click();
    await expect(page.getByTestId("workbench-success")).toContainText("规则草稿已保存");

    const scheduleCard = page.getByTestId(`schedule-${schedule.id}`);
    await scheduleCard.getByRole("button", { name: "启用", exact: true }).click();
    await expect(page.getByTestId("workbench-success")).toContainText("调度已启用");
    await expect(scheduleCard).toContainText("启用");

    const rolePanel = page.getByTestId("role-layout-admin");
    await expect(rolePanel).toBeVisible();
    await rolePanel.getByRole("button", { name: "配置" }).first().click();
    await expect(page.getByTestId("role-layout-drawer")).toBeVisible();
    await page.getByTestId("role-layout-save").click();
    await expect(page.getByTestId("workbench-success")).toContainText("默认布局已保存");
  });
});
