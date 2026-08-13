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

test.describe("work orders and collection", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("work order start complete cancel", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("WoPark"), address: "wo" },
    });
    const parkId = (park.body as { data: { id: number } }).data.id;
    const title = uniqueName("WO");

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/work-orders");
    await page.getByTestId("wo-park-id").fill(String(parkId));
    await page.getByTestId("wo-title").fill(title);
    await page.getByTestId("wo-create-btn").click();
    await expect(page.getByTestId("wo-success")).toContainText(/创建/, { timeout: 15000 });
    await expect(page.getByTestId("wo-table")).toContainText(title);

    const listed = await apiJson(request, "get", "/work-orders?page=1&page_size=50", { token });
    const items = (listed.body as { data: { items: Array<{ id: number; title: string }> } }).data
      .items;
    const woId = items.find((x) => x.title === title)!.id;

    const row = page.locator(`[data-testid=wo-row-${woId}]`);
    if (await row.getByTestId("wo-start-btn").count()) {
      await row.getByTestId("wo-start-btn").click();
      await expect(page.getByTestId("wo-success")).toContainText(/开始/, { timeout: 15000 });
    }
    await row.getByTestId("wo-complete-btn").click();
    await expect(page.getByTestId("wo-success")).toContainText(/完成/, { timeout: 15000 });

    // second order cancel path
    const title2 = uniqueName("WO-C");
    await page.getByTestId("wo-park-id").fill(String(parkId));
    await page.getByTestId("wo-title").fill(title2);
    await page.getByTestId("wo-create-btn").click();
    await expect(page.getByTestId("wo-table")).toContainText(title2, { timeout: 15000 });
    const listed2 = await apiJson(request, "get", "/work-orders?page=1&page_size=50", { token });
    const items2 = (listed2.body as { data: { items: Array<{ id: number; title: string }> } }).data
      .items;
    const wo2 = items2.find((x) => x.title === title2)!.id;
    await page.locator(`[data-testid=wo-row-${wo2}]`).getByTestId("wo-cancel-btn").click();
    await expect(page.getByTestId("wo-success")).toContainText(/取消/, { timeout: 15000 });
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
