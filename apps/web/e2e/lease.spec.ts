import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import {
  ADMIN_PASS,
  ADMIN_USER,
  LEASE_SUBMITTER_PASS,
  LEASE_SUBMITTER_USER,
  LEASE_VIEWER_PASS,
  LEASE_VIEWER_USER,
  apiJson,
  apiLogin,
  loginAs,
  requireApiHealthy,
  uniqueName,
} from "./helpers";

type LeaseFixture = {
  token: string;
  parkId: number;
  partyId: number;
  unitId: number;
};

async function createLeaseFixture(
  request: APIRequestContext,
  prefix: string
): Promise<LeaseFixture> {
  const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
  const park = await apiJson(request, "post", "/parks", {
    token,
    data: { name: uniqueName(`${prefix}Park`), address: `${prefix}-road` },
  });
  expect(park.status).toBe(200);
  const parkId = (park.body as { data: { id: number } }).data.id;
  const unit = await apiJson(request, "post", "/units", {
    token,
    data: {
      park_id: parkId,
      name: `${prefix}-101`,
      code: uniqueName(prefix).slice(0, 20),
      rentable_area: 120,
      status: "VACANT",
    },
  });
  expect(unit.status).toBe(200);
  const unitId = (unit.body as { data: { id: number } }).data.id;
  const party = await apiJson(request, "post", "/parties", {
    token,
    data: { name: uniqueName(`${prefix}Party`), party_type: "ORGANIZATION" },
  });
  expect(party.status).toBe(200);
  const partyId = (party.body as { data: { id: number } }).data.id;
  return { token, parkId, partyId, unitId };
}

async function createDraftViaApi(
  request: APIRequestContext,
  fixture: LeaseFixture,
  token = fixture.token
): Promise<number> {
  const created = await apiJson(request, "post", "/leases", {
    token,
    data: {
      park_id: fixture.parkId,
      party_id: fixture.partyId,
      start_date: "2099-01-01",
      end_date: "2099-12-31",
      deposit_amount: "5000",
      units: [
        {
          unit_id: fixture.unitId,
          occupied_area: "80",
          unit_rent_price: "0",
        },
      ],
      charges: [
        {
          charge_code: "RENT",
          charge_type: "RENT",
          calculation_method: "FIXED",
          billing_cycle: "MONTHLY",
          start_date: "2099-01-01",
          end_date: "2099-12-31",
          due_day: 5,
          amount: "1200",
          tax_rate: "0",
        },
      ],
    },
  });
  expect(created.status).toBe(200);
  return (created.body as { data: { id: number } }).data.id;
}

async function createAndActivateThroughUi(
  page: Page,
  request: APIRequestContext,
  prefix: string
): Promise<LeaseFixture & { contractId: number }> {
  const fixture = await createLeaseFixture(request, prefix);
  await loginAs(page, ADMIN_USER, ADMIN_PASS);
  await page.goto("/leases");
  await page.getByRole("button", { name: "新建合同草稿" }).click();
  await page.getByTestId("lease-park-id").selectOption(String(fixture.parkId));
  await page.getByTestId("lease-party-id").selectOption(String(fixture.partyId));
  await page.getByTestId("lease-unit-id").selectOption(String(fixture.unitId));
  await page.getByTestId("lease-start").fill("2099-01-01");
  await page.getByTestId("lease-end").fill("2099-12-31");
  await page.getByTestId("lease-area").fill("80");
  await page.getByTestId("lease-deposit").fill("5000");
  await page.getByLabel("固定金额").fill("1200");
  await page.getByTestId("lease-create-btn").click();
  await expect(page.getByTestId("lease-success")).toContainText("履约计划预览");
  await page.getByRole("button", { name: "审批文档" }).click();
  await page.getByRole("button", { name: "提交审批" }).click();
  await expect(page.getByTestId("lease-success")).toContainText("提交审批");
  await page.getByRole("button", { name: "批准", exact: true }).click();
  await expect(page.getByTestId("lease-success")).toContainText("审批已通过");
  await page.locator('input[type="file"]').first().setInputFiles({
    name: `${prefix}-contract.txt`,
    mimeType: "text/plain",
    buffer: Buffer.from(`synthetic ${prefix} contract`),
  });
  await page.getByRole("button", { name: "上传并追加" }).click();
  await expect(page.getByTestId("lease-success")).toContainText("主合同文档");
  await page.getByRole("button", { name: "批准版本" }).click();
  await expect(page.getByTestId("lease-success")).toContainText("文档已批准");
  await page.getByRole("button", { name: "激活合同" }).click();
  await expect(page.getByTestId("lease-success")).toContainText("未生成账单");

  const listed = await apiJson(request, "get", "/leases?page=1&page_size=100", {
    token: fixture.token,
  });
  const row = (
    listed.body as {
      data: { items: Array<{ id: number; party_id: number; status: string }> };
    }
  ).data.items.find(
    (item) => item.party_id === fixture.partyId && item.status === "ACTIVE"
  );
  expect(row).toBeTruthy();
  return { ...fixture, contractId: row!.id };
}

test.describe("contract lifecycle V2", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create, preview, approve document, activate and inspect immutable version", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept("E2E 管理员合成审批"));
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const parkName = uniqueName("ContractPark");
    const partyName = uniqueName("ContractParty");
    const unitCode = uniqueName("CV2").slice(0, 20);
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: parkName, address: "contract-v2-road" },
    });
    const parkId = (park.body as { data: { id: number } }).data.id;
    const unit = await apiJson(request, "post", "/units", {
      token,
      data: {
        park_id: parkId,
        name: "V2-101",
        code: unitCode,
        rentable_area: 120,
        status: "VACANT",
      },
    });
    const unitId = (unit.body as { data: { id: number } }).data.id;
    const party = await apiJson(request, "post", "/parties", {
      token,
      data: { name: partyName, party_type: "ORGANIZATION" },
    });
    const partyId = (party.body as { data: { id: number } }).data.id;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leases");
    await expect(page.getByTestId("leases-title")).toBeVisible();
    await page.getByRole("button", { name: "新建合同草稿" }).click();
    await page.getByTestId("lease-park-id").selectOption(String(parkId));
    await page.getByTestId("lease-party-id").selectOption(String(partyId));
    await page.getByTestId("lease-unit-id").selectOption(String(unitId));
    await page.getByTestId("lease-start").fill("2099-01-01");
    await page.getByTestId("lease-end").fill("2099-12-31");
    await page.getByTestId("lease-area").fill("80");
    await page.getByTestId("lease-deposit").fill("5000");
    await page.getByLabel("固定金额").fill("1200");
    await page.getByTestId("lease-create-btn").click();
    await expect(page.getByTestId("lease-success")).toContainText("履约计划预览", {
      timeout: 15000,
    });

    await page.getByRole("button", { name: "审批文档" }).click();
    await page.getByRole("button", { name: "提交审批" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("提交审批");
    await page.getByRole("button", { name: "批准", exact: true }).click();
    await expect(page.getByTestId("lease-success")).toContainText("审批已通过");

    await page.locator('input[type="file"]').first().setInputFiles({
      name: "contract-v2.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("synthetic contract lifecycle v2"),
    });
    await page.getByRole("button", { name: "上传并追加" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("主合同文档");
    await page.getByRole("button", { name: "批准版本" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("文档已批准");
    await page.getByRole("button", { name: "激活合同" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("未生成账单", {
      timeout: 15000,
    });

    await page.getByRole("button", { name: "版本", exact: true }).click();
    await expect(page.getByText(/版本 V1/)).toBeVisible();
    await expect(page.getByText(/INITIAL_ACTIVATION/)).toBeVisible();

    const listed = await apiJson(request, "get", "/leases?page=1&page_size=100", { token });
    expect(listed.status).toBe(200);
    const rows = (listed.body as { data: { items: Array<{ status: string; party_id: number }> } })
      .data.items;
    expect(rows.some((row) => row.party_id === partyId && row.status === "ACTIVE")).toBeTruthy();
  });

  test("workspace stays within tablet viewport and exposes keyboard focus targets", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leases");
    await expect(page.getByTestId("leases-title")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBeFalsy();
    const createButton = page.getByRole("button", { name: "新建合同草稿" });
    await createButton.focus();
    await expect(createButton).toBeFocused();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "新建合同草稿" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByLabel("园区")).toBeVisible();
    await dialog.getByRole("button", { name: "关闭" }).focus();
    await expect(dialog.getByRole("button", { name: "关闭" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(dialog).toHaveCount(0);
  });

  test("typed renewal applies as immutable V2 with API/UI reconciliation", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept("E2E 管理员合成审批"));
    const fixture = await createAndActivateThroughUi(page, request, "Change");
    const lifecycle = await apiJson(
      request,
      "get",
      `/leases/${fixture.contractId}/lifecycle`,
      { token: fixture.token }
    );
    const snapshot = JSON.parse(
      JSON.stringify((lifecycle.body as { data: { current_snapshot: unknown } }).data.current_snapshot)
    ) as {
      contract: Record<string, unknown>;
      charges: Array<Record<string, unknown>>;
    };
    snapshot.contract.end_date = "2100-12-31";
    snapshot.charges.forEach((charge) => {
      charge.end_date = "2100-12-31";
    });

    await page.getByRole("button", { name: "合同变更", exact: true }).click();
    await page.getByLabel("变更类型").selectOption("RENEWAL");
    await page.getByLabel("生效日").fill("2100-01-01");
    await page.getByLabel("变更原因").fill("E2E 续租一年");
    await page.getByLabel("完整未来快照").fill(JSON.stringify(snapshot, null, 2));
    await expect(page.getByTestId("draft-change-diff")).toContainText("contract.end_date");
    await page.getByRole("button", { name: "创建变更草稿" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("变更草稿已创建");
    await page.getByRole("button", { name: "提交", exact: true }).click();
    await page.getByRole("button", { name: "批准", exact: true }).click();
    await page.getByRole("button", { name: "应用到期变更" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("变更已应用");

    const reconciled = await apiJson(
      request,
      "get",
      `/leases/${fixture.contractId}/lifecycle`,
      { token: fixture.token }
    );
    const data = reconciled.body as {
      data: {
        contract: { end_date: string; current_version_no: number };
        changes: Array<{ status: string }>;
      };
    };
    expect(data.data.contract.end_date).toBe("2100-12-31");
    expect(data.data.contract.current_version_no).toBe(2);
    expect(data.data.changes.some((change) => change.status === "APPLIED")).toBeTruthy();
  });

  test("exit clearance closes contract without money movement and releases projection", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept("E2E 管理员合成审批"));
    const fixture = await createAndActivateThroughUi(page, request, "Exit");
    await page.getByRole("button", { name: "退租结算", exact: true }).click();
    await page.getByLabel("计划交接日").fill("2099-06-01");
    await page.getByLabel("验房说明").fill("E2E 验房完成");
    await page.getByRole("button", { name: "创建退租草稿" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("占用仍保留");
    await page.getByRole("button", { name: "提交退租审批" }).click();
    await page.getByRole("button", { name: "批准退租" }).click();
    await page.getByLabel("外部清账凭证").setInputFiles({
      name: "exit-clearance.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("synthetic external clearance evidence"),
    });
    await page.getByLabel("外部引用").fill("E2E-CLEARANCE-001");
    await page.getByLabel("复核原因").fill("线下账务已由独立复核人确认");
    await page.getByRole("button", { name: "确认外部清账证据" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("系统未执行收退款");
    await page.getByRole("button", { name: "关闭退租并释放占用" }).click();
    await expect(page.getByTestId("lease-success")).toContainText("未执行资金操作");

    const reconciled = await apiJson(
      request,
      "get",
      `/leases/${fixture.contractId}/lifecycle`,
      { token: fixture.token }
    );
    const data = reconciled.body as {
      data: {
        contract: { status: string; current_version_no: number };
        units: unknown[];
        exit_settlement: { status: string; financial_clearance_status: string };
      };
    };
    expect(data.data.contract.status).toBe("TERMINATED");
    expect(data.data.contract.current_version_no).toBe(2);
    // Contract-unit lines are immutable historical facts. Releasing occupancy
    // changes the current Unit projection, not the signed contract snapshot.
    expect(data.data.units).toHaveLength(1);
    expect(data.data.exit_settlement.status).toBe("CLOSED");
    expect(data.data.exit_settlement.financial_clearance_status).toBe("CONFIRMED");
    const unit = await apiJson(request, "get", `/units/${fixture.unitId}`, {
      token: fixture.token,
    });
    expect(unit.status).toBe(200);
    expect(
      (unit.body as { data: { status: string; used_area: number } }).data
    ).toMatchObject({ status: "VACANT", used_area: 0 });
  });

  test("read-only user sees facts without mutation controls", async ({ page, request }) => {
    const fixture = await createLeaseFixture(request, "ReadOnly");
    const contractId = await createDraftViaApi(request, fixture);
    await loginAs(page, LEASE_VIEWER_USER, LEASE_VIEWER_PASS);
    await page.goto("/leases");
    await expect(page.getByTestId("leases-title")).toBeVisible();
    await expect(page.getByRole("button", { name: "新建合同草稿" })).toHaveCount(0);
    const row = page.getByTestId(`lease-row-${contractId}`);
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "查看" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: "审批文档" }).click();
    await expect(page.getByRole("button", { name: "提交审批" })).toHaveCount(0);
    await expect(page.getByText("追加主合同文档")).toHaveCount(0);
  });

  test("self approval 403 preserves pending state and surfaces business code", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept("不得绕过职责分离"));
    const fixture = await createLeaseFixture(request, "SelfApproval");
    const submitterToken = await apiLogin(
      request,
      LEASE_SUBMITTER_USER,
      LEASE_SUBMITTER_PASS
    );
    const contractId = await createDraftViaApi(request, fixture, submitterToken);
    await loginAs(page, LEASE_SUBMITTER_USER, LEASE_SUBMITTER_PASS);
    await page.goto("/leases");
    await page.getByTestId(`lease-row-${contractId}`).getByRole("button", { name: "查看" }).click();
    await page.getByRole("button", { name: "审批文档" }).click();
    await page.getByRole("button", { name: "提交审批" }).click();
    await page.getByRole("button", { name: "批准", exact: true }).click();
    await expect(page.getByTestId("lease-error")).toContainText(
      "LEASE_SELF_APPROVAL_FORBIDDEN"
    );
    const state = await apiJson(request, "get", `/leases/${contractId}/lifecycle`, {
      token: submitterToken,
    });
    expect((state.body as { data: { contract: { status: string } } }).data.contract.status).toBe(
      "PENDING_APPROVAL"
    );
  });

  test("stale 409 refresh warning preserves the opened draft context", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept("E2E 管理员合成审批"));
    const fixture = await createLeaseFixture(request, "Stale");
    const contractId = await createDraftViaApi(request, fixture);
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leases");
    await page.getByTestId(`lease-row-${contractId}`).getByRole("button", { name: "查看" }).click();
    await page.getByRole("button", { name: "审批文档" }).click();
    const before = await apiJson(request, "get", `/leases/${contractId}/lifecycle`, {
      token: fixture.token,
    });
    const currentLockVersion = (
      before.body as { data: { contract: { lock_version: number } } }
    ).data.contract.lock_version;
    const submitted = await apiJson(
      request,
      "post",
      `/leases/${contractId}/lifecycle/submit`,
      { token: fixture.token, data: { expected_version: currentLockVersion } }
    );
    expect(submitted.status).toBe(200);
    await page.getByRole("button", { name: "提交审批" }).click();
    await expect(page.getByTestId("lease-error")).toContainText("LEASE_VERSION_CONFLICT");
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("provider and backend 503 states are explicit and recoverable", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept("E2E 管理员合成审批"));
    await page.route("**/api/v1/leases?**", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          code: "LEASE_BACKEND_UNAVAILABLE",
          message: "合同查询暂不可用",
          data: null,
        }),
      })
    );
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/leases");
    await expect(page.getByTestId("lease-error")).toContainText("LEASE_BACKEND_UNAVAILABLE");
    await page.unroute("**/api/v1/leases?**");
    const fixture = await createAndActivateThroughUi(page, request, "Provider503");
    await page.route("**/api/v1/leases/*/documents/*/sign", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          code: "SIGNATURE_PROVIDER_NOT_CONFIGURED",
          message: "电子签章服务未配置",
          data: null,
        }),
      })
    );
    await page.getByRole("button", { name: "审批文档" }).click();
    await page.getByRole("button", { name: "签署", exact: true }).click();
    await expect(page.getByTestId("lease-error")).toContainText(
      "SIGNATURE_PROVIDER_NOT_CONFIGURED"
    );
    const state = await apiJson(
      request,
      "get",
      `/leases/${fixture.contractId}/lifecycle`,
      { token: fixture.token }
    );
    const documents = (state.body as { data: { documents: Array<{ status: string }> } }).data
      .documents;
    expect(documents.some((document) => document.status === "APPROVED")).toBeTruthy();
  });
});
