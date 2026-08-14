import { test, expect } from "@playwright/test";
import { createHash, createHmac } from "node:crypto";
import {
  ADMIN_PASS,
  ADMIN_USER,
  apiBase,
  apiJson,
  apiLogin,
  loginAs,
  requireApiHealthy,
  uniqueName,
} from "./helpers";

async function seedParkAndUnit(request: Parameters<typeof apiLogin>[0], token: string) {
  const parkName = uniqueName("招商验收园");
  const parkResult = await apiJson(request, "post", "/parks", {
    token,
    data: { name: parkName, address: "crm-e2e" },
  });
  expect(parkResult.status).toBe(200);
  const parkId = (parkResult.body as { data: { id: number } }).data.id;
  const suffix = uniqueName("CRM").replace(/-/g, "").slice(-10).toUpperCase();
  const space = await apiJson(request, "post", "/spaces", {
    token,
    data: {
      park_id: parkId,
      code: `B${suffix}`,
      name: `招商楼栋${suffix}`,
      node_type: "BUILDING",
    },
  });
  expect(space.status).toBe(200);
  const buildingId = (space.body as { data: { id: number } }).data.id;
  const unit = await apiJson(request, "post", "/units", {
    token,
    data: {
      park_id: parkId,
      building_id: buildingId,
      code: `U${suffix}`,
      name: `招商单元${suffix}`,
      rentable_area: 120,
      usage_type: "FACTORY",
      base_rent_price: 30,
      status: "VACANT",
    },
  });
  expect(unit.status).toBe(200);
  return {
    parkId,
    parkName,
    unitId: (unit.body as { data: { id: number } }).data.id,
  };
}

async function publishIntentDefinition(
  request: Parameters<typeof apiLogin>[0],
  token: string,
  code: string
) {
  const created = await apiJson(request, "post", "/approval-definitions", {
    token,
    data: {
      code,
      name: `招商意向审批-${code.slice(-8)}`,
      biz_type: "LEAD_INTENT",
      steps: [
        {
          step_order: 1,
          name: "园区经理审批",
          approval_mode: "ANY",
          min_approvals: 1,
          sla_hours: 24,
          assignees: [{ user_id: 1 }],
        },
      ],
    },
  });
  expect(created.status).toBe(200);
  const definition = (created.body as {
    data: { id: number; versions: Array<{ id: number; status: string }> };
  }).data;
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

test.describe("investment CRM V2", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create, viewing, governed intent, lock and atomic conversion", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const seeded = await seedParkAndUnit(request, token);
    const leadName = uniqueName("招商主路径客户");
    const phone = `137${String(Date.now()).slice(-8)}`;
    const definitionCode = uniqueName("LEAD_INTENT").replace(/-/g, "_").toUpperCase();
    await publishIntentDefinition(request, token, definitionCode);

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    await expect(page.getByTestId("leads-title")).toBeVisible();
    await page.getByTestId("lead-create-open").click();
    await page.getByTestId("lead-park-id").selectOption({ label: seeded.parkName });
    await page.getByTestId("lead-name").fill(leadName);
    await page.getByTestId("lead-phone").fill(phone);
    await page.getByTestId("lead-intent").selectOption("HIGH");
    await page.getByLabel("意向面积（㎡）").fill("100");
    await page.getByLabel("预算单价").fill("35");
    await page.getByTestId("lead-create-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText("线索已创建");
    await expect(page.getByTestId("lead-detail")).toContainText(leadName);
    const listedLead = await apiJson(
      request,
      "get",
      `/leads?keyword=${encodeURIComponent(leadName)}`,
      { token }
    );
    const leadId = (listedLead.body as { data: { items: Array<{ id: number }> } }).data.items[0].id;

    await page.getByTestId("lead-activity-open").click();
    await page.getByTestId("lead-edit-status").selectOption("CONTACTING");
    await page.getByTestId("lead-remark").fill("确认需求并约定带看");
    await page.getByTestId("lead-update-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText("跟进活动已记录");
    await expect(page.getByTestId("lead-detail")).toContainText("联系中");

    await page.getByTestId("unit-match-load").click();
    const match = page.getByTestId(`unit-match-${seeded.unitId}`);
    await expect(match).toContainText("90/100");
    await expect(match).toContainText("与意向面积相差 20.00");
    await expect(match).toContainText("用途匹配 FACTORY");

    const viewingStart = new Date(Date.now() + 24 * 60 * 60 * 1000);
    const viewingEnd = new Date(viewingStart.getTime() + 60 * 60 * 1000);
    await page.getByTestId("viewing-create-open").click();
    await page.getByLabel("开始时间").fill(viewingStart.toISOString().slice(0, 16));
    await page.getByLabel("结束时间").fill(viewingEnd.toISOString().slice(0, 16));
    await page.getByLabel("访客姓名").fill("企业选址负责人");
    await page.getByRole("button", { name: "确认排期" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("带看已排期");
    const viewingPanel = page.getByTestId("lead-viewings");
    await viewingPanel.getByRole("button", { name: "确认", exact: true }).click();
    await expect(page.getByTestId("lead-success")).toContainText("带看已确认");
    await viewingPanel.getByTestId("viewing-complete-open").click();
    await page.getByTestId("viewing-outcome").fill("厂房条件匹配，进入意向审批");
    await page.getByRole("button", { name: "完成并归档" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("带看结果已归档");

    await page.getByTestId("unit-match-load").click();
    await expect(page.getByTestId(`unit-match-${seeded.unitId}`)).toBeVisible();
    await page.getByTestId("intent-create-open").click();
    await page.getByLabel("申请面积（㎡）").fill("100");
    await page.getByLabel("意向单价").fill("35");
    await page.getByLabel("租期开始").fill("2026-10-01");
    await page.getByLabel("租期结束").fill("2027-09-30");
    await page.getByLabel("意向有效至").fill("2026-09-30T18:00");
    await page.getByRole("button", { name: "冻结意向版本" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("意向草稿已创建");
    await page.getByTestId("intent-submit-open").click();
    await page.getByTestId("intent-definition-code").fill(definitionCode);
    await page.getByRole("button", { name: "提交统一审批" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("意向已提交审批");

    const intentResult = await apiJson(request, "get", `/leads/${leadId}/intent`, { token });
    const intent = (intentResult.body as {
      data: { id: number; approval_request_id: number; status: string };
    }).data;
    expect(intent.status).toBe("PENDING");
    const tasksResult = await apiJson(request, "get", "/approval-tasks?biz_type=LEAD_INTENT", {
      token,
    });
    const task = (
      tasksResult.body as {
        data: {
          items: Array<{
            id: number;
            approval_id: number;
            approval_lock_version: number;
          }>;
        };
      }
    ).data.items.find((row) => row.approval_id === intent.approval_request_id);
    expect(task).toBeTruthy();
    const decision = await apiJson(request, "post", `/approval-tasks/${task!.id}/decide`, {
      token,
      data: {
        action: "APPROVE",
        remark: "E2E 同意锁房",
        expected_version: task!.approval_lock_version,
        idempotency_key: uniqueName("intent-approve"),
        override_reason: "E2E 合成管理员执行单人审批",
      },
    });
    expect(decision.status).toBe(200);

    await page.reload();
    await page.getByTestId("lead-keyword").fill(leadName);
    await page.getByTestId("lead-filter-btn").click();
    await page.getByTestId("lead-list-view").click();
    await page.locator(`[data-testid=lead-row-${leadId}]`).getByRole("button", { name: "详情" }).click();
    await expect(page.getByTestId("lead-intent-panel")).toContainText("APPROVED");
    await page.getByTestId("unit-match-load").click();
    const approvedMatch = page.getByTestId(`unit-match-${seeded.unitId}`);
    await expect(approvedMatch.getByRole("button", { name: "锁定 48 小时" })).toBeEnabled();
    await approvedMatch.getByRole("button", { name: "锁定 48 小时" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("房源已锁定");
    await expect(page.getByTestId("lead-detail")).toContainText(`单元 #${seeded.unitId}`);

    await page.getByTestId("lead-convert-btn").click();
    await page.getByLabel("开始日期").fill("2026-10-01");
    await page.getByLabel("结束日期").fill("2027-09-30");
    await page.getByLabel("占用面积").fill("100");
    await page.getByLabel("租金单价").fill("35");
    await page.getByTestId("lead-convert-confirm").click();
    await expect(page.getByTestId("lead-success")).toContainText("主体与合同草稿已原子创建");
    await expect(page.getByTestId("lead-detail")).toContainText("已转化");

    const detail = await apiJson(request, "get", `/leads/${leadId}`, { token });
    const body = (detail.body as {
      data: { status: string; lease_id: number; unit_locks: Array<{ lease_id: number; status: string }> };
    }).data;
    expect(body.status).toBe("WON");
    expect(body.lease_id).toBeGreaterThan(0);
    expect(body.unit_locks[0].lease_id).toBe(body.lease_id);
    expect(body.unit_locks[0].status).toBe("ACTIVE");
  });

  test("governance UI creates and publishes a rule while channels remain explicit", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const seeded = await seedParkAndUnit(request, token);
    const suffix = String(Date.now()).slice(-10);
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");

    const rulePanel = page.getByTestId("assignment-rule-panel");
    await rulePanel.locator("summary").click();
    await rulePanel.getByTestId("assignment-rule-create").click();
    await page
      .getByTestId("assignment-rule-form")
      .locator("select")
      .first()
      .selectOption(String(seeded.parkId));
    await page.getByLabel("规则编码").fill(`E2E_RULE_${suffix}`);
    await page.getByLabel("规则名称").fill("E2E 自动分配规则");
    await page.getByRole("button", { name: "创建草稿" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("分配规则草稿已创建");
    await expect(rulePanel).toContainText("E2E 自动分配规则");
    await rulePanel.getByRole("button", { name: "发布" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("分配规则已发布");
    await expect(rulePanel).toContainText("v1");
    await expect(rulePanel).toContainText("ACTIVE");

    const channelPanel = page.getByTestId("lead-channel-panel");
    await channelPanel.locator("summary").click();
    await channelPanel.getByTestId("lead-channel-create").click();
    await page
      .getByTestId("lead-channel-form")
      .locator("select")
      .selectOption(String(seeded.parkId));
    await page.getByLabel("渠道编码").fill(`E2E_CHANNEL_${suffix}`);
    await page.getByLabel("渠道名称").fill("E2E 待联调渠道");
    await page.getByLabel("密钥环境变量名").fill(`KWZY_E2E_CHANNEL_${suffix}`);
    await page.getByRole("button", { name: "保存渠道配置" }).click();
    await expect(page.getByTestId("lead-success")).toContainText("渠道配置已创建");
    await expect(channelPanel).toContainText("默认关闭");
    await expect(channelPanel).toContainText("NOT_CONNECTED");

    const liveChannelResult = await apiJson(request, "post", "/crm/channels", {
      token,
      data: {
        park_id: seeded.parkId,
        code: `E2E_SIGNED_${suffix}`,
        name: "E2E 签名接收渠道",
        secret_env_key: "KWZY_E2E_LEAD_CHANNEL_SECRET",
        enabled: true,
        allow_auto_assign: false,
      },
    });
    expect(liveChannelResult.status).toBe(200);
    const liveChannel = (liveChannelResult.body as {
      data: { id: number; public_id: string; verification_status: string };
    }).data;
    expect(liveChannel.verification_status).toBe("NOT_CONNECTED");
    const rawBody = JSON.stringify({
      name: `E2E 渠道客户-${suffix}`,
      contact_phone: `136${suffix.slice(-8)}`,
      intent_area: "75",
    });
    const eventId = `evt-${suffix}`;
    const timestamp = String(Math.floor(Date.now() / 1000));
    const bodySha = createHash("sha256").update(rawBody).digest("hex");
    const signature = createHmac("sha256", "e2e-local-channel-secret-32-bytes")
      .update(`v1\n${timestamp}\n${eventId}\n${bodySha}`)
      .digest("hex");
    const signedHeaders = {
      "Content-Type": "application/json",
      "X-KWZY-Timestamp": timestamp,
      "X-KWZY-Event-Id": eventId,
      "X-KWZY-Signature": `v1=${signature}`,
    };
    const accepted = await request.post(
      `${apiBase()}/public/lead-channels/${liveChannel.public_id}/events`,
      { headers: signedHeaders, data: rawBody }
    );
    expect(accepted.status()).toBe(200);
    const acceptedEvent = (await accepted.json()) as {
      data: { id: number; status: string; lead_id: number };
    };
    expect(acceptedEvent.data.status).toBe("ACCEPTED");
    expect(acceptedEvent.data.lead_id).toBeGreaterThan(0);
    const verifiedChannel = await apiJson(request, "get", `/crm/channels/${liveChannel.id}`, {
      token,
    });
    expect(
      (verifiedChannel.body as { data: { verification_status: string } }).data.verification_status
    ).toBe("LOCAL_CONTRACT_VERIFIED");
    const repeated = await request.post(
      `${apiBase()}/public/lead-channels/${liveChannel.public_id}/events`,
      { headers: signedHeaders, data: rawBody }
    );
    expect(repeated.status()).toBe(200);
    expect(((await repeated.json()) as { data: { id: number } }).data.id).toBe(
      acceptedEvent.data.id
    );
  });

  test("duplicate override stays in context and public lead can be claimed", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const seeded = await seedParkAndUnit(request, token);
    const duplicateName = uniqueName("重复招商客户");
    const phone = `136${String(Date.now()).slice(-8)}`;
    const first = await apiJson(request, "post", "/leads", {
      token,
      data: {
        park_id: seeded.parkId,
        name: duplicateName,
        contact_phone: phone,
      },
    });
    expect(first.status).toBe(200);

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    await page.getByTestId("lead-create-open").click();
    await page.getByTestId("lead-park-id").selectOption({ label: seeded.parkName });
    await page.getByTestId("lead-name").fill(duplicateName);
    await page.getByTestId("lead-phone").fill(phone);
    await page.getByTestId("lead-create-btn").click();
    await expect(page.getByTestId("lead-duplicate-panel")).toContainText("PHONE");
    await page.getByTestId("lead-override-reason").fill("同一联系电话下的独立选址项目");
    await page.getByTestId("lead-create-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText("线索已创建");

    const publicName = uniqueName("公海客户");
    const createdPublic = await apiJson(request, "post", "/leads", {
      token,
      data: {
        park_id: seeded.parkId,
        name: publicName,
        contact_phone: `135${String(Date.now() + 1).slice(-8)}`,
        pool_status: "PUBLIC",
      },
    });
    expect(createdPublic.status).toBe(200);
    await page.getByTestId("lead-pool-filter").selectOption("PUBLIC");
    await page.getByTestId("lead-keyword").fill(publicName);
    await page.getByTestId("lead-filter-btn").click();
    await page.getByTestId("lead-list-view").click();
    const row = page.locator(`[data-testid=lead-row-${(createdPublic.body as { data: { id: number } }).data.id}]`);
    await expect(row).toContainText(publicName);
    await row.getByTestId("lead-claim-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText("公海线索已领取");
  });

  test("stale write refreshes safely and read-only controls stay hidden", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const seeded = await seedParkAndUnit(request, token);
    const created = await apiJson(request, "post", "/leads", {
      token,
      data: {
        park_id: seeded.parkId,
        name: uniqueName("冲突恢复客户"),
        contact_phone: `134${String(Date.now()).slice(-8)}`,
      },
    });
    const lead = (created.body as { data: { id: number; lock_version: number } }).data;
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    await page.getByTestId("lead-list-view").click();
    await page.locator(`[data-testid=lead-row-${lead.id}]`).getByRole("button", { name: "详情" }).click();
    await expect(page.getByTestId("lead-detail")).toBeVisible();

    const concurrent = await apiJson(request, "patch", `/leads/${lead.id}`, {
      token,
      data: { expected_version: lead.lock_version, remark: "并发请求先提交" },
    });
    expect(concurrent.status).toBe(200);
    await page.getByTestId("lead-activity-open").click();
    await page.getByTestId("lead-remark").fill("保留输入但触发版本冲突");
    await page.getByTestId("lead-update-btn").click();
    await expect(page.getByTestId("lead-error")).toContainText("数据已刷新");
    await expect(page.getByTestId("lead-detail")).toContainText("并发请求先提交");

    await loginAs(page, "e2e_crm_viewer", "viewer123");
    await page.goto("/leads");
    await expect(page.getByTestId("leads-title")).toBeVisible();
    await expect(page.getByTestId("lead-create-open")).toHaveCount(0);
    await expect(page.getByTestId("lead-claim-btn")).toHaveCount(0);
  });

  test("manager assignment, public release, reclaim and merge stay auditable", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const seeded = await seedParkAndUnit(request, token);
    const sourceName = uniqueName("待合并招商客户");
    const targetName = uniqueName("保留招商客户");
    const create = async (name: string, phonePrefix: string) => {
      const result = await apiJson(request, "post", "/leads", {
        token,
        data: {
          park_id: seeded.parkId,
          name,
          contact_phone: `${phonePrefix}${String(Date.now()).slice(-8)}`,
        },
      });
      expect(result.status).toBe(200);
      return (result.body as { data: { id: number } }).data.id;
    };
    const sourceId = await create(sourceName, "132");
    const targetId = await create(targetName, "131");

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    await page.getByLabel("授权园区").selectOption({ label: seeded.parkName });
    await page.getByTestId("lead-filter-btn").click();
    await page.getByTestId("lead-list-view").click();
    await page.locator(`[data-testid=lead-row-${sourceId}]`).getByRole("button", { name: "详情" }).click();

    await page.getByTestId("lead-assign-open").click();
    await page.getByTestId("lead-assignee").selectOption({ label: "招商只读用户" });
    await page.getByTestId("lead-assign-reason").fill("经理按行业专长转派");
    await page.getByTestId("lead-assign-submit").click();
    await expect(page.getByTestId("lead-success")).toContainText("负责人已更新");
    await expect(page.getByTestId("lead-detail")).toContainText("REASSIGN");
    await expect(page.getByTestId("lead-detail")).toContainText("招商只读用户");

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByTestId("lead-release-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText("线索已释放到公海");
    await expect(page.getByTestId("lead-detail")).toContainText("RELEASE");
    await page.getByTestId("lead-detail").getByTestId("lead-claim-btn").click();
    await expect(page.getByTestId("lead-success")).toContainText("公海线索已领取");
    await expect(page.getByTestId("lead-detail")).toContainText("CLAIM");

    await page.getByTestId("lead-merge-open").click();
    await page.getByTestId("lead-merge-target").selectOption(String(targetId));
    await page.getByTestId("lead-merge-reason").fill("核验为同一招商机会，保留主记录");
    await page.getByTestId("lead-merge-submit").click();
    await expect(page.getByTestId("lead-success")).toContainText("重复线索已合并");
    await expect(page.getByTestId("lead-detail")).toContainText(targetName);

    const source = await apiJson(request, "get", `/leads/${sourceId}`, { token });
    expect((source.body as { data: { status: string; merged_into_lead_id: number } }).data).toMatchObject({
      status: "MERGED",
      merged_into_lead_id: targetId,
    });
    const target = await apiJson(request, "get", `/leads/${targetId}`, { token });
    expect((target.body as { data: { merged_sources: number[] } }).data.merged_sources).toContain(sourceId);
  });

  test("workspace exposes an explicit recoverable backend failure", async ({ page }) => {
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.route("**/api/v1/crm/summary**", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ code: "CRM_TEMPORARILY_UNAVAILABLE", message: "招商服务暂不可用" }),
      });
    });
    await page.goto("/leads");
    await expect(page.getByTestId("lead-error")).toContainText("招商服务暂不可用");
    await page.unroute("**/api/v1/crm/summary**");
    await page.getByTestId("lead-filter-btn").click();
    await expect(page.getByTestId("lead-error")).toHaveCount(0);
    await expect(page.getByTestId("leads-title")).toBeVisible();
  });

  test("tablet layout keeps primary controls keyboard reachable", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leads");
    await expect(page.getByTestId("leads-title")).toBeVisible();
    await page.getByTestId("lead-board-view").focus();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("lead-list-view")).toBeFocused();
    await page.getByTestId("lead-create-open").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("lead-create-form")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("lead-create-form")).toHaveCount(0);
  });

  test("mobile loading, empty, forbidden and offline states retry without overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);

    const summaryPattern = "**/api/v1/crm/summary**";
    let releaseLoading!: () => void;
    const loadingGate = new Promise<void>((resolve) => {
      releaseLoading = resolve;
    });
    await page.route(summaryPattern, async (route) => {
      await loadingGate;
      await route.continue();
    });
    await page.goto("/leads");
    await expect(page.getByText("正在校准招商数据…")).toBeVisible();
    releaseLoading();
    await expect(page.getByText("正在校准招商数据…")).toHaveCount(0);
    await page.unroute(summaryPattern);

    await page.getByTestId("lead-list-view").click();
    await page.getByTestId("lead-keyword").fill(uniqueName("不存在的招商客户"));
    await page.getByTestId("lead-filter-btn").click();
    await expect(page.getByText("没有符合筛选条件的线索")).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    ).toBe(true);

    await page.route(summaryPattern, async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ code: "PERMISSION_DENIED", message: "无权读取招商汇总" }),
      });
    });
    await page.getByTestId("lead-filter-btn").click();
    await expect(page.getByTestId("lead-error")).toContainText("无权读取招商汇总");
    await page.unroute(summaryPattern);

    await page.route(summaryPattern, async (route) => route.abort("internetdisconnected"));
    await page.getByTestId("lead-filter-btn").click();
    await expect(page.getByTestId("lead-error")).toContainText("Network Error");
    await page.unroute(summaryPattern);
    await page.getByTestId("lead-filter-btn").click();
    await expect(page.getByTestId("lead-error")).toHaveCount(0);
    await expect(page.getByText("没有符合筛选条件的线索")).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    ).toBe(true);
  });
});
