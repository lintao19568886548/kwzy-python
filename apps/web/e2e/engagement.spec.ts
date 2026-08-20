import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
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
const evidenceDir = path.resolve(
  __dirname,
  "../../../docs/06-implementation/evidence/park-enterprise-policy-service-engagement"
);

function dataOf<T>(body: unknown): T {
  return (body as { data: T }).data;
}

async function publishApprovalDefinition(
  request: APIRequestContext,
  token: string,
  code: string,
  bizType: string
) {
  const created = await apiJson(request, "post", "/approval-definitions", {
    token,
    data: {
      code,
      name: `${bizType} 浏览器独立验收审批`,
      biz_type: bizType,
      steps: [
        {
          step_order: 1,
          name: "园区企业服务负责人复核",
          approval_mode: "ANY",
          min_approvals: 1,
          sla_hours: 24,
          assignees: [{ user_id: 1 }],
        },
      ],
    },
  });
  expect(created.status).toBe(200);
  const definition = dataOf<{
    id: number;
    versions: Array<{ id: number; status: string }>;
  }>(created.body);
  const draft = definition.versions.find((row) => row.status === "DRAFT");
  expect(draft).toBeTruthy();
  const published = await apiJson(
    request,
    "post",
    `/approval-definitions/${definition.id}/publish`,
    { token, data: { version_id: draft!.id, expected_lock_version: 0 } }
  );
  expect(published.status).toBe(200);
}

async function approveNativeApproval(
  request: APIRequestContext,
  token: string,
  approvalId: number,
  key: string
) {
  const detailResult = await apiJson(request, "get", `/approvals/${approvalId}`, { token });
  expect(detailResult.status).toBe(200);
  const detail = dataOf<{
    lock_version: number;
    tasks: Array<{ id: number; status: string }>;
  }>(detailResult.body);
  const task = detail.tasks.find((row) => row.status === "PENDING");
  expect(task).toBeTruthy();
  const decision = await apiJson(request, "post", `/approval-tasks/${task!.id}/decide`, {
    token,
    data: {
      action: "APPROVE",
      expected_version: detail.lock_version,
      idempotency_key: key,
      override_reason: "企业参与浏览器 E2E 独立验收审批门禁",
    },
  });
  expect(decision.status).toBe(200);
}

async function submitApproveAndPublish(
  page: Page,
  request: APIRequestContext,
  token: string,
  kind: "policies" | "services" | "activities" | "announcements",
  code: string,
  definitionCode: string,
  card: ReturnType<Page["locator"]>,
  publishButton: string
) {
  page.once("dialog", (dialog) => dialog.accept(definitionCode));
  await card.getByRole("button", { name: "提交审批" }).click();
  await expect(page.getByTestId("engagement-success")).toContainText("已提交原生审批");

  const list = await apiJson(request, "get", `/engagement/staff/${kind}`, { token });
  expect(list.status).toBe(200);
  const aggregate = dataOf<
    Array<{ code: string; version: { approval_id: number | null } }>
  >(list.body).find((row) => row.code === code);
  expect(aggregate?.version.approval_id).toBeTruthy();
  await approveNativeApproval(
    request,
    token,
    aggregate!.version.approval_id!,
    `engagement-e2e-approve-${kind}-${code}`
  );

  await card.getByRole("button", { name: publishButton, exact: true }).click();
  await expect(page.getByTestId("engagement-success")).toContainText("已发布审批通过的精确版本");
  await expect(card).toContainText("PUBLISHED");
}

test.describe("park enterprise policy service engagement", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("real staff and tenant-principal journeys with responsive and offline truth", async ({
    page,
    request,
    context,
  }) => {
    test.setTimeout(240000);
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const suffix = uniqueName("eng").replace(/-/g, "").slice(-9).toUpperCase();
    const parkResponse = await apiJson(request, "post", "/parks", {
      token,
      data: { name: `企业参与验收园 ${suffix}`, address: "engagement-e2e" },
    });
    expect(parkResponse.status).toBe(200);
    const parkId = dataOf<{ id: number }>(parkResponse.body).id;

    const partyResponse = await apiJson(request, "post", "/parties", {
      token,
      data: {
        name: `E2E 企业主体 ${suffix}`,
        party_type: "ORGANIZATION",
        initial_park_relation: { park_id: parkId, role_code: "LESSEE" },
      },
    });
    expect(partyResponse.status).toBe(200);
    const party = dataOf<{ id: number }>(partyResponse.body);

    const tenantRoleResponse = await apiJson(request, "post", "/system/roles", {
      token,
      data: {
        code: `ENGAGEMENT_TENANT_${suffix}`,
        name: `企业参与租户角色${suffix}`,
        permission_codes: [
          "engagement:read",
          "engagement:service_request",
          "engagement:activity_register",
        ],
        park_ids: [parkId],
        all_parks: false,
      },
    });
    expect(tenantRoleResponse.status).toBe(200);
    const tenantRole = dataOf<{ id: number }>(tenantRoleResponse.body);
    const tenantUsername = `eng_tenant_${suffix.toLowerCase()}`;
    const tenantPassword = "Engagement-Tenant!2026";
    const tenantUserResponse = await apiJson(request, "post", "/system/users", {
      token,
      data: {
        username: tenantUsername,
        password: tenantPassword,
        real_name: `企业参与租户${suffix}`,
        role_ids: [tenantRole.id],
        park_ids: [parkId],
        all_parks: false,
      },
    });
    expect(tenantUserResponse.status).toBe(200);
    const tenantUser = dataOf<{ id: number }>(tenantUserResponse.body);
    const principal = await apiJson(request, "post", "/tenant-service/principals", {
      token,
      data: { user_id: tenantUser.id, party_id: party.id, park_ids: [parkId] },
    });
    expect(principal.status).toBe(200);

    const definitions = {
      policies: `ENG_POLICY_${suffix}`,
      services: `ENG_SERVICE_${suffix}`,
      activities: `ENG_ACTIVITY_${suffix}`,
      announcements: `ENG_ANNOUNCEMENT_${suffix}`,
    };
    await publishApprovalDefinition(
      request,
      token,
      definitions.policies,
      "ENGAGEMENT_POLICY"
    );
    await publishApprovalDefinition(
      request,
      token,
      definitions.services,
      "ENGAGEMENT_SERVICE"
    );
    await publishApprovalDefinition(
      request,
      token,
      definitions.activities,
      "ENGAGEMENT_ACTIVITY"
    );
    await publishApprovalDefinition(
      request,
      token,
      definitions.announcements,
      "ENGAGEMENT_ANNOUNCEMENT"
    );

    const policyCode = `POL_${suffix}`;
    const policyTitle = `本地产业政策 ${suffix}`;
    const serviceCode = `SVC_${suffix}`;
    const serviceTitle = `企业合规辅导 ${suffix}`;
    const activityCode = `ACT_${suffix}`;
    const activityTitle = `园区政策说明会 ${suffix}`;
    const announcementCode = `ANN_${suffix}`;
    const announcementTitle = `园区服务公告 ${suffix}`;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/engagement");
    await expect(page.getByTestId("engagement-title")).toBeVisible();
    await expect(page.getByTestId("engagement-truth")).toContainText(
      "本地相关性 ≠ 官方资格"
    );
    await expect(page.getByTestId("engagement-truth")).toContainText("生产触达：否");

    await page.getByTestId("engagement-tab-policies").click();
    await page.getByTestId("engagement-add-policy").click();
    const policyDrawer = page.getByTestId("engagement-drawer");
    await policyDrawer.getByLabel("园区 ID").fill(String(parkId));
    await policyDrawer.getByLabel("政策编码").fill(policyCode);
    await policyDrawer.getByLabel("标题").fill(policyTitle);
    await policyDrawer.getByLabel("分类").fill("INDUSTRY");
    await policyDrawer.getByLabel("正文").fill("仅表达园区本地相关性，不构成政府资格认定。");
    await policyDrawer.getByRole("button", { name: "保存政策草稿" }).click();
    await expect(page.getByTestId("engagement-success")).toContainText("政策草稿已建立");
    const policyCard = page.locator("article.item-card").filter({ hasText: policyTitle });
    await submitApproveAndPublish(
      page,
      request,
      token,
      "policies",
      policyCode,
      definitions.policies,
      policyCard,
      "发布已批准版本"
    );

    await page.getByTestId("engagement-tab-services").click();
    await page.getByTestId("engagement-add-service").click();
    const serviceDrawer = page.getByTestId("engagement-drawer");
    await serviceDrawer.getByLabel("园区 ID").fill(String(parkId));
    await serviceDrawer.getByLabel("服务编码").fill(serviceCode);
    await serviceDrawer.getByLabel("标题").fill(serviceTitle);
    await serviceDrawer.getByLabel("描述").fill("园区内部服务，不连接外部服务商。");
    await serviceDrawer.getByLabel("SLA 小时").fill("24");
    await serviceDrawer.getByRole("button", { name: "保存服务草稿" }).click();
    const serviceCard = page.locator("article.item-card").filter({ hasText: serviceTitle });
    await submitApproveAndPublish(
      page,
      request,
      token,
      "services",
      serviceCode,
      definitions.services,
      serviceCard,
      "发布"
    );
    await expect(serviceCard).toContainText("园区企业服务中心 · LOCAL");

    await page.getByTestId("engagement-tab-activities").click();
    await page.getByTestId("engagement-add-activity").click();
    const activityDrawer = page.getByTestId("engagement-drawer");
    await activityDrawer.getByLabel("园区 ID").fill(String(parkId));
    await activityDrawer.getByLabel("活动编码").fill(activityCode);
    await activityDrawer.getByLabel("标题").fill(activityTitle);
    await activityDrawer.getByLabel("描述").fill("真实报名、容量和签到链路独立验收。");
    await activityDrawer.getByLabel("地点").fill("园区会议中心 A 厅");
    await activityDrawer.getByLabel("容量").fill("2");
    await activityDrawer.getByRole("button", { name: "保存活动草稿" }).click();
    const activityCard = page.locator("article.item-card").filter({ hasText: activityTitle });
    await submitApproveAndPublish(
      page,
      request,
      token,
      "activities",
      activityCode,
      definitions.activities,
      activityCard,
      "发布"
    );

    await page.getByTestId("engagement-tab-announcements").click();
    await page.getByTestId("engagement-add-announcement").click();
    const announcementDrawer = page.getByTestId("engagement-drawer");
    await announcementDrawer.getByLabel("园区 ID").fill(String(parkId));
    await announcementDrawer.getByLabel("公告编码").fill(announcementCode);
    await announcementDrawer.getByLabel("标题").fill(announcementTitle);
    await announcementDrawer.getByLabel("正文").fill("仅站内信送达，不代表短信或外部渠道触达。");
    await announcementDrawer.getByLabel("优先级").selectOption("IMPORTANT");
    await announcementDrawer.getByRole("button", { name: "保存公告草稿" }).click();
    const announcementCard = page.locator("article.item-card").filter({
      hasText: announcementTitle,
    });
    await submitApproveAndPublish(
      page,
      request,
      token,
      "announcements",
      announcementCode,
      definitions.announcements,
      announcementCard,
      "发布 / 定时"
    );
    await page.getByRole("button", { name: "处理站内分发" }).click();
    await expect(page.getByTestId("engagement-success")).toContainText("外部渠道仍未连接");
    await expect(page.getByTestId("engagement-loading")).toBeHidden();

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "engagement-staff-desktop.png"),
      fullPage: true,
    });

    await loginAs(page, tenantUsername, tenantPassword);
    await page.goto("/engagement?tab=policies");
    await expect(page.getByTestId("engagement-mode-staff")).toHaveCount(0);
    await expect(page.getByTestId("engagement-mode-tenant")).toHaveClass(/active/);
    const tenantPolicyCard = page.locator("article.item-card").filter({ hasText: policyTitle });
    await tenantPolicyCard.getByRole("button", { name: "相关性匹配" }).click();
    await expect(tenantPolicyCard).toContainText("本地相关");
    page.once("dialog", (dialog) => dialog.accept("请说明本园区服务适用范围"));
    await tenantPolicyCard.getByRole("button", { name: "本地咨询" }).click();
    await expect(page.getByTestId("engagement-success")).toContainText("未向政府系统申报");

    await page.getByTestId("engagement-tab-services").click();
    const tenantServiceCard = page.locator("article.item-card").filter({ hasText: serviceTitle });
    page.once("dialog", (dialog) => dialog.accept("需要一次企业合规辅导"));
    await tenantServiceCard.getByRole("button", { name: "申请服务" }).click();
    await expect(page.getByTestId("engagement-success")).toContainText("绑定当前企业主体");
    await expect(page.getByText(serviceTitle).last()).toBeVisible();

    await page.getByTestId("engagement-tab-activities").click();
    const tenantActivityCard = page.locator("article.item-card").filter({
      hasText: activityTitle,
    });
    await tenantActivityCard.getByRole("button", { name: "报名" }).click();
    await expect(page.getByTestId("engagement-success")).toContainText("活动报名已记录");
    await expect(page.getByText(/报名 #/)).toBeVisible();

    await page.setViewportSize({ width: 820, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "engagement-tenant-tablet.png"),
      fullPage: true,
    });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    ).toBe(true);

    await page.getByTestId("engagement-tab-announcements").click();
    await expect(page.getByText(announcementTitle).first()).toBeVisible();
    const inboxRow = page.locator("article.case-row").filter({ hasText: announcementTitle });
    await inboxRow.getByRole("button", { name: "标记已读" }).click();
    await expect(inboxRow).toContainText("READ");

    await page.setViewportSize({ width: 390, height: 844 });
    await context.setOffline(true);
    await expect(page.getByTestId("engagement-offline")).toContainText("不会展示伪成功");
    await page.screenshot({
      path: path.join(evidenceDir, "engagement-mobile-offline.png"),
      fullPage: true,
    });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    ).toBe(true);
    await context.setOffline(false);
  });
});
