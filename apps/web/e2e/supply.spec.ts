import { expect, test } from "@playwright/test";
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
  "../../../docs/06-implementation/evidence/supply-procurement-inventory-outsourcing"
);

function dataOf<T>(body: unknown): T {
  return (body as { data: T }).data;
}

async function publishApprovalDefinition(
  request: Parameters<typeof apiLogin>[0],
  token: string,
  code: string,
  bizType: string
) {
  const created = await apiJson(request, "post", "/approval-definitions", {
    token,
    data: {
      code,
      name: `${bizType} E2E 独立验收审批`,
      biz_type: bizType,
      steps: [
        {
          step_order: 1,
          name: "独立验收负责人复核",
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
  request: Parameters<typeof apiLogin>[0],
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
      override_reason: "供应链浏览器 E2E 独立验收管理员审批门禁",
    },
  });
  expect(decision.status).toBe(200);
}

test.describe("supply procurement inventory outsourcing", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("real supply UI journey, responsive layout and offline retry", async ({ page, request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/parks", {
          token,
          data: { name: uniqueName("SupplyPark"), address: "supply-e2e" },
        })
      ).body
    );
    const party = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/parties", {
          token,
          data: {
            name: uniqueName("SupplyVendor"),
            party_type: "ORGANIZATION",
            credit_code: `91310000MA1F${Date.now().toString().slice(-6)}`,
          },
        })
      ).body
    );
    await apiJson(request, "post", `/parties/${party.id}/roles`, {
      token,
      data: { role_code: "SUPPLIER" },
    });
    const suffix = uniqueName("supply").replace(/-/g, "").slice(-8).toUpperCase();
    const supplierName = `E2E 受控供应商 ${suffix}`;
    const credentialNumber = `E2E-SECRET-${suffix}-9988`;
    const materialName = `E2E 防水材料 ${suffix}`;
    const warehouseName = `E2E 维修主仓 ${suffix}`;
    const procurementPurpose = `E2E 季度维修采购 ${suffix}`;
    const inventoryPurpose = `E2E 现场维修领用 ${suffix}`;
    const outsourcingTitle = `E2E 屋面防水外包 ${suffix}`;
    const procurementDefinition = `SUPPLY_PROC_${suffix}`;
    const inventoryDefinition = `SUPPLY_INV_${suffix}`;
    const outsourcingDefinition = `SUPPLY_OUT_${suffix}`;

    await publishApprovalDefinition(
      request,
      token,
      procurementDefinition,
      "PROCUREMENT_REQUISITION"
    );
    await publishApprovalDefinition(
      request,
      token,
      inventoryDefinition,
      "INVENTORY_REQUISITION"
    );
    await publishApprovalDefinition(
      request,
      token,
      outsourcingDefinition,
      "OUTSOURCING_ORDER"
    );

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/supply");
    await expect(page.getByTestId("supply-title")).toBeVisible();
    await expect(page.getByText("ERP/WMS/供应商门户")).toBeVisible();
    await expect(page.getByText("未连接").first()).toBeVisible();

    await page.getByTestId("supply-tab-suppliers").click();
    await page.getByTestId("supply-add-supplier").click();
    await page.getByLabel("企业主体 ID").fill(String(party.id));
    await page.getByLabel("供应商编码").fill(`SUP_${suffix}`);
    await page.getByLabel("显示名称").fill(supplierName);
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByRole("button", { name: "建立主体关联和园区范围" }).click();
    await expect(page.getByTestId("supply-success")).toContainText("供应商与园区范围已建立");
    await expect(page.getByText(supplierName)).toBeVisible();
    const supplierCard = page.getByRole("article").filter({ hasText: supplierName });
    await supplierCard.getByRole("button", { name: "登记资质" }).click();
    const qualificationDrawer = page.getByTestId("supply-drawer");
    await qualificationDrawer.getByLabel("资质类型").fill("SAFETY_LICENSE");
    await qualificationDrawer.getByLabel("证件号").fill(credentialNumber);
    await qualificationDrawer.getByLabel("签发机构").fill("E2E 园区安全管理机构");
    await qualificationDrawer.getByLabel("生效日期").fill("2026-01-01");
    await qualificationDrawer.getByLabel("到期日期").fill("2028-12-31");
    await qualificationDrawer.getByRole("button", { name: "登记受控资质" }).click();
    await expect(page.getByTestId("supply-success")).toContainText("供应商资质已登记");
    await expect(supplierCard).toContainText("SAFETY_LICENSE");
    await expect(supplierCard).not.toContainText(credentialNumber);
    page.once("dialog", (dialog) => dialog.accept("E2E 资格复核暂停"));
    await supplierCard.getByRole("button", { name: "暂停" }).click();
    await expect(supplierCard).toContainText("SUSPENDED");
    page.once("dialog", (dialog) => dialog.accept("E2E 复核完成恢复"));
    await supplierCard.getByRole("button", { name: "恢复" }).click();
    await expect(supplierCard).toContainText("ACTIVE");

    await page.getByTestId("supply-tab-inventory").click();
    await page.getByRole("button", { name: "新增物料" }).click();
    await page.getByLabel("物料编码").fill(`MAT_${suffix}`);
    await page.getByLabel("名称").fill(materialName);
    await page.getByLabel("补货线").fill("2");
    await page.getByRole("button", { name: "建立物料" }).click();
    await expect(page.getByText("物料已建立")).toBeVisible();
    await page.getByRole("button", { name: "新增仓库" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("仓库编码").fill(`WH_${suffix}`);
    await page.getByLabel("仓库名称").fill(warehouseName);
    await page.getByRole("button", { name: "建立园区仓库" }).click();
    await expect(page.getByText("仓库已建立")).toBeVisible();

    await page.getByTestId("supply-tab-procurement").click();
    await page.getByRole("button", { name: "新建申请" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("用途").fill(procurementPurpose);
    await page.getByLabel("物料").selectOption({ label: `MAT_${suffix} · ${materialName}` });
    await page.getByLabel("数量").fill("10");
    await page.getByLabel("估算单价").fill("35");
    await page.getByRole("button", { name: "保存采购草稿" }).click();
    await expect(page.getByText("采购申请草稿已建立")).toBeVisible();
    await expect(page.getByText(procurementPurpose)).toBeVisible();
    const procurementRow = page.locator("tbody tr").filter({ hasText: procurementPurpose });
    await procurementRow.getByRole("button", { name: "编辑" }).click();
    await page.getByLabel("估算单价").fill("36");
    await page.getByRole("button", { name: "更新采购草稿" }).click();
    await expect(page.getByTestId("supply-success")).toContainText("采购申请草稿已更新");
    await procurementRow.getByRole("button", { name: "提交审批" }).click();
    await page.getByLabel("审批定义编码").fill(procurementDefinition);
    await page.getByRole("button", { name: "提交原生审批" }).click();
    await expect(procurementRow).toContainText("PENDING_APPROVAL");

    const procurementResult = await apiJson(
      request,
      "get",
      "/supply/procurement/requisitions",
      { token }
    );
    expect(procurementResult.status).toBe(200);
    const procurement = dataOf<
      Array<{ id: number; purpose: string; approval_id: number; status: string }>
    >(procurementResult.body).find((row) => row.purpose === procurementPurpose);
    expect(procurement?.status).toBe("PENDING_APPROVAL");
    await approveNativeApproval(
      request,
      token,
      procurement!.approval_id,
      uniqueName("supply-procurement-approve")
    );
    await procurementRow.getByRole("button", { name: "同步审批" }).click();
    await expect(procurementRow).toContainText("APPROVED");
    await procurementRow.getByRole("button", { name: "建立订单" }).click();
    const orderDrawer = page.getByTestId("supply-drawer");
    await orderDrawer
      .getByLabel("供应商")
      .selectOption({ label: `SUP_${suffix} · ${supplierName}` });
    await orderDrawer.getByLabel("统一单价").fill("36");
    await orderDrawer.getByRole("button", { name: "建立本地采购订单" }).click();
    await expect(page.getByTestId("supply-success")).toContainText("采购订单已建立");
    const orderCard = page.getByRole("article").filter({ hasText: supplierName });
    page.once("dialog", (dialog) => dialog.accept());
    await orderCard.getByRole("button", { name: "确认订单" }).click();
    await expect(orderCard).toContainText("ACKNOWLEDGED");
    page.once("dialog", (dialog) => dialog.accept());
    await orderCard.getByRole("button", { name: "收货剩余" }).click();
    await expect(orderCard).toContainText("RECEIVED");

    await page.getByTestId("supply-tab-inventory").click();
    await page.getByRole("button", { name: "领用申请" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("用途").fill(inventoryPurpose);
    await page.getByLabel("仓库").selectOption({ label: `WH_${suffix} · ${warehouseName}` });
    await page.getByLabel("物料").selectOption({ label: `MAT_${suffix} · ${materialName}` });
    await page.getByLabel("数量").fill("2");
    await page.getByRole("button", { name: "保存领用草稿" }).click();
    await expect(page.getByText("领用申请草稿已建立")).toBeVisible();
    const inventoryCard = page.getByRole("article").filter({ hasText: inventoryPurpose });
    await inventoryCard.getByRole("button", { name: "提交审批" }).click();
    await page.getByLabel("审批定义编码").fill(inventoryDefinition);
    await page.getByRole("button", { name: "提交原生审批" }).click();
    await expect(inventoryCard).toContainText("PENDING_APPROVAL");
    const inventoryResult = await apiJson(
      request,
      "get",
      "/supply/inventory/requisitions",
      { token }
    );
    const inventoryRequest = dataOf<
      Array<{ id: number; purpose: string; approval_id: number; status: string }>
    >(inventoryResult.body).find((row) => row.purpose === inventoryPurpose);
    expect(inventoryRequest?.status).toBe("PENDING_APPROVAL");
    await approveNativeApproval(
      request,
      token,
      inventoryRequest!.approval_id,
      uniqueName("supply-inventory-approve")
    );
    await inventoryCard.getByRole("button", { name: "同步审批" }).click();
    await expect(inventoryCard).toContainText("APPROVED");
    page.once("dialog", (dialog) => dialog.accept());
    await inventoryCard.getByRole("button", { name: "发放剩余" }).click();
    await expect(inventoryCard).toContainText("ISSUED");

    const balanceRow = page
      .getByTestId("supply-balance-table")
      .locator("tbody tr")
      .filter({ hasText: materialName })
      .filter({ hasText: warehouseName });
    await expect(balanceRow).toContainText("8.0000");

    await page.getByRole("button", { name: "新建盘点" }).click();
    await page
      .getByTestId("supply-drawer")
      .getByLabel("仓库")
      .selectOption({ label: `WH_${suffix} · ${warehouseName}` });
    await page
      .getByTestId("supply-drawer")
      .getByLabel("物料")
      .selectOption({ label: `MAT_${suffix} · ${materialName}` });
    await page.getByLabel("实盘数量").fill("8");
    await page.getByRole("button", { name: "保存盘点草稿" }).click();
    await expect(page.getByTestId("supply-success")).toContainText("盘点草稿已建立");
    const warehouseResult = await apiJson(request, "get", "/supply/warehouses", { token });
    expect(warehouseResult.status).toBe(200);
    const warehouse = dataOf<Array<{ id: number; code: string }>>(warehouseResult.body).find(
      (row) => row.code === `WH_${suffix}`
    );
    expect(warehouse).toBeTruthy();
    const stocktakeResult = await apiJson(request, "get", "/supply/inventory/stocktakes", {
      token,
    });
    expect(stocktakeResult.status).toBe(200);
    const stocktake = dataOf<
      Array<{
        stocktake_no: string;
        warehouse_id: number;
        status: string;
        approval_id: number | null;
      }>
    >(stocktakeResult.body).find((row) => row.warehouse_id === warehouse!.id);
    expect(stocktake?.status).toBe("DRAFT");
    const stocktakeRow = page
      .locator(".compact-list p")
      .filter({ hasText: stocktake!.stocktake_no });
    await stocktakeRow.getByRole("button", { name: "提交", exact: true }).click();
    await page.getByLabel("审批定义编码").fill(inventoryDefinition);
    await page.getByRole("button", { name: "提交原生审批" }).click();
    await expect(stocktakeRow).toContainText("APPROVED");
    page.once("dialog", (dialog) => dialog.accept());
    await stocktakeRow.getByRole("button", { name: "批准后过账" }).click();
    await expect(stocktakeRow).toContainText("POSTED");

    await page.getByTestId("supply-tab-outsourcing").click();
    await page.getByRole("button", { name: "新建外包" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("供应商").selectOption({ label: `SUP_${suffix} · ${supplierName}` });
    await page.getByLabel("服务标题").fill(outsourcingTitle);
    await page.getByLabel("SLA 截止").fill("2026-12-31T18:00");
    await page.getByLabel("金额").fill("3000");
    await page.getByRole("button", { name: "保存外包草稿" }).click();
    await expect(page.getByText("外包服务草稿已建立")).toBeVisible();
    const outsourcingCard = page.getByRole("article").filter({ hasText: outsourcingTitle });
    await expect(outsourcingCard.getByText("NOT_INTEGRATED", { exact: false })).toBeVisible();
    await outsourcingCard.getByRole("button", { name: "提交审批" }).click();
    await page.getByLabel("审批定义编码").fill(outsourcingDefinition);
    await page.getByRole("button", { name: "提交原生审批" }).click();
    await expect(outsourcingCard).toContainText("PENDING_APPROVAL");
    const outsourcingResult = await apiJson(
      request,
      "get",
      "/supply/outsourcing/orders",
      { token }
    );
    const outsourcingOrder = dataOf<
      Array<{ id: number; title: string; approval_id: number; status: string }>
    >(outsourcingResult.body).find((row) => row.title === outsourcingTitle);
    expect(outsourcingOrder?.status).toBe("PENDING_APPROVAL");
    await approveNativeApproval(
      request,
      token,
      outsourcingOrder!.approval_id,
      uniqueName("supply-outsourcing-approve")
    );
    await outsourcingCard.getByRole("button", { name: "同步审批" }).click();
    await expect(outsourcingCard).toContainText("APPROVED");
    await outsourcingCard.getByRole("button", { name: "开始履约" }).click();
    await expect(outsourcingCard).toContainText("IN_PROGRESS");
    page.once("dialog", (dialog) => dialog.accept());
    await outsourcingCard.getByRole("button", { name: "提交验收" }).click();
    await expect(outsourcingCard).toContainText("WAITING_ACCEPTANCE");
    page.once("dialog", (dialog) => dialog.accept());
    await outsourcingCard.getByRole("button", { name: "退回返工" }).click();
    await expect(outsourcingCard).toContainText("REWORK");
    await outsourcingCard.getByRole("button", { name: "开始履约" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await outsourcingCard.getByRole("button", { name: "提交验收" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await outsourcingCard.getByRole("button", { name: "验收通过" }).click();
    await expect(outsourcingCard).toContainText("ACCEPTED");

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "pc-desktop-supply-outsourcing.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 820, height: 1180 });
    await page.getByTestId("supply-tab-procurement").click();
    await page.screenshot({
      path: path.join(evidenceDir, "pc-tablet-supply-procurement.png"),
      fullPage: true,
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/v1/supply/**", (route) => route.abort("failed"));
    await page.getByTestId("supply-refresh").click();
    await expect(page.getByTestId("supply-error")).toBeVisible();
    const layout = await page.evaluate(() => {
      const viewport = document.documentElement.clientWidth;
      const tabs = Array.from(document.querySelectorAll<HTMLElement>(".tabs button")).map((node) =>
        node.getBoundingClientRect()
      );
      return {
        bodyFits: document.body.scrollWidth <= document.body.clientWidth + 1,
        tabsFit: tabs.every((rect) => rect.left >= 0 && rect.right <= viewport + 1),
      };
    });
    expect(layout.bodyFits).toBe(true);
    expect(layout.tabsFit).toBe(true);
    await page.screenshot({
      path: path.join(evidenceDir, "pc-mobile-supply-offline-retry.png"),
      fullPage: true,
    });
  });
});
