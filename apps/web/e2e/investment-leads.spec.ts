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

test.describe("investment CRM V2", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create, follow, explainable match, lock and atomic conversion", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const seeded = await seedParkAndUnit(request, token);
    const leadName = uniqueName("招商主路径客户");
    const phone = `137${String(Date.now()).slice(-8)}`;

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
    await match.getByRole("button", { name: "锁定 48 小时" }).click();
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

    const listed = await apiJson(
      request,
      "get",
      `/leads?keyword=${encodeURIComponent(leadName)}`,
      { token }
    );
    const lead = (listed.body as { data: { items: Array<{ id: number }> } }).data.items[0];
    const detail = await apiJson(request, "get", `/leads/${lead.id}`, { token });
    const body = (detail.body as {
      data: { status: string; lease_id: number; unit_locks: Array<{ lease_id: number; status: string }> };
    }).data;
    expect(body.status).toBe("WON");
    expect(body.lease_id).toBeGreaterThan(0);
    expect(body.unit_locks[0].lease_id).toBe(body.lease_id);
    expect(body.unit_locks[0].status).toBe("ACTIVE");
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
});
