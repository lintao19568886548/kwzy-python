import { test, expect } from "@playwright/test";
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
  "../../../docs/06-implementation/evidence/tenant-service-work-order-lifecycle"
);

function dataOf<T>(body: unknown): T {
  return (body as { data: T }).data;
}

test.describe("work orders and collection", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("staff and tenant complete quote, fulfillment, acceptance, rating and isolation", async ({
    page,
    request,
  }) => {
    const adminToken = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/parks", {
          token: adminToken,
          data: { name: uniqueName("WoPark"), address: "tenant-service-e2e" },
        })
      ).body
    );
    const createParty = async (prefix: string) => {
      const response = await apiJson(request, "post", "/parties", {
        token: adminToken,
        data: {
          name: uniqueName(prefix),
          party_type: "ORGANIZATION",
          initial_park_relation: { park_id: park.id, role_code: "LESSEE" },
        },
      });
      expect(response.status).toBe(200);
      return dataOf<{ id: number }>(response.body);
    };
    const partyA = await createParty("WoPartyA");
    const partyB = await createParty("WoPartyB");
    const suffix = uniqueName("tenant").replace(/-/g, "").slice(-10).toLowerCase();
    const createTenant = async (partyId: number, marker: string) => {
      const permissions = [
        "tenant_service:request",
        "tenant_service:read_own",
        "tenant_service:quote_decide",
        "tenant_service:accept",
        "tenant_service:rate",
      ];
      const roleResponse = await apiJson(request, "post", "/system/roles", {
        token: adminToken,
        data: {
          code: `TENANT_SERVICE_${marker}_${suffix}`.toUpperCase(),
          name: `租户服务角色${marker}${suffix}`,
          permission_codes: permissions,
          park_ids: [park.id],
          all_parks: false,
        },
      });
      expect(roleResponse.status).toBe(200);
      const role = dataOf<{ id: number }>(roleResponse.body);
      const username = `tenant_${marker.toLowerCase()}_${suffix}`;
      const password = "Tenant-Service!2026";
      const userResponse = await apiJson(request, "post", "/system/users", {
        token: adminToken,
        data: {
          username,
          password,
          real_name: `租户用户${marker}`,
          role_ids: [role.id],
          park_ids: [park.id],
          all_parks: false,
        },
      });
      expect(userResponse.status).toBe(200);
      const user = dataOf<{ id: number }>(userResponse.body);
      const principal = await apiJson(request, "post", "/tenant-service/principals", {
        token: adminToken,
        data: { user_id: user.id, party_id: partyId, park_ids: [park.id] },
      });
      expect(principal.status).toBe(200);
      return { username, password };
    };
    const tenantA = await createTenant(partyA.id, "A");
    const tenantB = await createTenant(partyB.id, "B");
    const operatorResponse = await apiJson(request, "post", "/system/users", {
      token: adminToken,
      data: {
        username: `operator_${suffix}`,
        password: "Operator-Service!2026",
        real_name: "工单执行人",
        role_ids: [],
        park_ids: [],
        all_parks: true,
      },
    });
    expect(operatorResponse.status).toBe(200);
    const operator = dataOf<{ id: number }>(operatorResponse.body);
    const title = uniqueName("WO-LIFECYCLE");

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/work-orders");
    await page.getByTestId("wo-open-intake").click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("企业主体 ID").fill(String(partyA.id));
    await page.getByLabel("标题").fill(title);
    await page.getByLabel("问题描述").fill("空调机组异响，需要报价后维修");
    await page.getByLabel("此工单执行前需要租户确认报价").check();
    await page.getByTestId("wo-create-btn").click();
    await expect(page.getByTestId("wo-success")).toContainText("服务请求已受理");
    await expect(page.getByTestId("wo-drawer")).toContainText(title);

    await page.getByPlaceholder("处理人用户 ID").fill(String(operator.id));
    await page.getByPlaceholder("派单 / 改派原因").fill("自动规则未命中，值班经理派单");
    await page.getByRole("button", { name: "确认派单" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("派单已保存");
    await page.getByTestId("wo-start-btn").click();
    await expect(page.getByTestId("wo-success")).toContainText("工单已接单");

    const quoteForm = page.locator("form.form-card").filter({ hasText: "新建报价版本" });
    await quoteForm.getByPlaceholder("报价项目").fill("更换空调轴承");
    await quoteForm.getByPlaceholder("数量").fill("2");
    await quoteForm.getByPlaceholder("单位").fill("个");
    await quoteForm.getByPlaceholder("单价").fill("80");
    await quoteForm.getByRole("button", { name: "保存报价草稿" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("报价草稿已创建");
    await page.getByRole("button", { name: "提交租户确认" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("报价已提交租户确认");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "pc-desktop-work-order-quote-waiting.png"),
      fullPage: false,
    });

    await loginAs(page, tenantA.username, tenantA.password);
    await page.goto("/work-orders");
    await expect(page.getByTestId("work-orders-title")).toContainText("企业服务中心");
    await page.getByTestId("wo-table").getByText(title).click();
    await page.getByRole("button", { name: "提交报价决定" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("报价决定已提交");

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/work-orders");
    await page.getByTestId("wo-table").getByText(title).click();
    const costForm = page.locator("form.form-card").filter({ hasText: "登记实际成本" });
    await costForm.getByPlaceholder("成本说明").fill("空调轴承实耗");
    await costForm.getByPlaceholder("数量").fill("2");
    await costForm.getByPlaceholder("单位").fill("个");
    await costForm.getByPlaceholder("单价").fill("75");
    await costForm.getByRole("button", { name: "登记成本" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("实际成本已登记");
    await page.getByPlaceholder("处理结果").fill("轴承更换完成，连续运行测试通过");
    await page.getByPlaceholder("无证据时填写原因").fill("现场证据由纸质设备卡留存");
    await page.getByTestId("wo-complete-btn").click();
    await expect(page.getByTestId("wo-success")).toContainText("完工结果已提交验收");

    await loginAs(page, tenantA.username, tenantA.password);
    await page.goto("/work-orders");
    await page.getByTestId("wo-table").getByText(title).click();
    await page.getByRole("button", { name: "提交验收决定" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("验收决定已提交");
    await page.getByPlaceholder("标签，以逗号分隔").fill("及时,专业");
    await page.getByPlaceholder("评价内容").fill("处理规范，结果清晰");
    await page.getByRole("button", { name: "提交不可修改的评价" }).click();
    await expect(page.getByTestId("wo-success")).toContainText("评价已提交");
    await expect(page.getByTestId("wo-drawer")).toContainText("已评价 5 分");
    await page.setViewportSize({ width: 390, height: 844 });
    const bodySize = await page.locator("body").evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(bodySize.scrollWidth).toBeLessThanOrEqual(bodySize.clientWidth + 1);
    await page.screenshot({
      path: path.join(evidenceDir, "pc-mobile-tenant-acceptance-rating.png"),
      fullPage: false,
    });

    await loginAs(page, tenantB.username, tenantB.password);
    await page.goto("/work-orders");
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
    await page.getByTestId("wo-open-intake").click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("标题").fill("离线报修草稿应保留");
    await page.route("**/api/v1/tenant-service/requests", (route) => route.abort("failed"));
    await page.getByTestId("wo-create-btn").click();
    await expect(page.getByTestId("wo-error")).toContainText("网络暂不可用");
    await expect(page.getByLabel("标题")).toHaveValue("离线报修草稿应保留");
    await page.screenshot({
      path: path.join(evidenceDir, "pc-mobile-tenant-offline-retry.png"),
      fullPage: true,
    });
  });

  test("collection case create update close + outbox fake", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("ColPark"), address: "col" },
    });
    const parkId = (park.body as { data: { id: number } }).data.id;
    const party = await apiJson(request, "post", "/parties", {
      token,
      data: { name: uniqueName("ColParty"), party_type: "ORGANIZATION" },
    });
    const partyId = (party.body as { data: { id: number } }).data.id;
    const bill = await apiJson(request, "post", "/bills", {
      token,
      data: {
        park_id: parkId,
        party_id: partyId,
        period_start: "2026-02-01",
        period_end: "2026-02-28",
        lines: [{ fee_code: "RENT", quantity: "1", unit_price: "100" }],
      },
    });
    const billId = (bill.body as { data: { id: number } }).data.id;
    await apiJson(request, "post", `/bills/${billId}/issue`, { token });

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/collection");
    await page.getByTestId("collection-park-id").fill(String(parkId));
    await page.getByTestId("collection-party-id").fill(String(partyId));
    await page.getByTestId("collection-bill-id").fill(String(billId));
    await page.getByTestId("collection-create-btn").click();
    await expect(page.getByTestId("collection-success")).toContainText(/创建/, { timeout: 15000 });

    const cases = await apiJson(request, "get", "/collection/cases?page=1&page_size=50", { token });
    const caseItems = (
      cases.body as { data: { items: Array<{ id: number; bill_id: number }> } }
    ).data.items;
    const caseId = caseItems.find((c) => c.bill_id === billId)!.id;

    await page.getByTestId("collection-update-id").fill(String(caseId));
    await page.getByTestId("collection-update-level").selectOption("L2");
    await page.getByTestId("collection-note").fill("催缴一次");
    await page.getByTestId("collection-update-btn").click();
    await expect(page.getByTestId("collection-success")).toContainText(/更新/, { timeout: 15000 });

    await page.locator(`[data-testid=collection-row-${caseId}]`).getByTestId("collection-close-btn").click();
    await expect(page.getByTestId("collection-success")).toContainText(/关闭/, { timeout: 15000 });

    // Exercise the configured NOT_LIVE SMS adapter with its real contract. A
    // missing route, permission failure, or invalid payload must fail the E2E.
    const idempotencyKey = `e2e-collection-sms-${caseId}`;
    const sms = await apiJson(request, "post", "/integrations/sms/send", {
      token,
      data: {
        to: "13800138000",
        template_code: "E2E",
        params: { case_id: caseId, bill_id: billId },
        idempotency_key: idempotencyKey,
      },
    });
    expect(sms.status).toBe(200);
    const smsData = (
      sms.body as { data: { provider: string; message_id: string; deduped: boolean } }
    ).data;
    expect(smsData.provider).toBe("fake");
    expect(smsData.message_id).toBeTruthy();
    expect(smsData.deduped).toBe(false);

    const outbox = await apiJson(request, "get", "/integrations/outbox", { token });
    expect(outbox.status).toBe(200);
    const outboxItems = (
      outbox.body as {
        data: Array<{ channel: string; provider: string; status: string; external_id: string }>;
      }
    ).data;
    expect(
      outboxItems.some(
        (item) =>
          item.channel === "sms" &&
          item.provider === "fake" &&
          item.status === "SUCCESS" &&
          item.external_id === smsData.message_id
      )
    ).toBe(true);
  });
});
