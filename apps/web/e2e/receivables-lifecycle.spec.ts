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
  "../../../docs/06-implementation/evidence/receivables-collection-lifecycle"
);

test.describe("receivables and collection lifecycle", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("receipt suggestion needs confirmation, overpayment remains unapplied and is allocated later", async ({
    page,
    request,
  }) => {
    page.on("dialog", (dialog) => dialog.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const parkResponse = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("ReceiptPark"), address: "receivables-e2e" },
    });
    const parkId = (parkResponse.body as { data: { id: number } }).data.id;
    const partyResponse = await apiJson(request, "post", "/parties", {
      token,
      data: { name: uniqueName("ReceiptParty"), party_type: "ORGANIZATION" },
    });
    const partyId = (partyResponse.body as { data: { id: number } }).data.id;
    const billResponse = await apiJson(request, "post", "/bills", {
      token,
      data: {
        park_id: parkId,
        party_id: partyId,
        period_start: "2099-01-01",
        period_end: "2099-01-31",
        due_date: "2099-02-05",
        lines: [{ fee_code: "RENT", quantity: "1", unit_price: "100" }],
      },
    });
    const bill = (billResponse.body as { data: { id: number; bill_no: string } }).data;
    expect((await apiJson(request, "post", `/bills/${bill.id}/issue`, { token })).status).toBe(200);

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/receipts");
    await expect(page.getByTestId("receipt-provider-status")).toContainText("NOT_CONNECTED");
    const sourceRef = uniqueName("BANK-RCP");
    await page.getByTestId("receipt-park-id").fill(String(parkId));
    await page.getByTestId("receipt-party-id").fill(String(partyId));
    await page.getByTestId("receipt-amount").fill("150");
    await page.getByTestId("receipt-source-ref").fill(sourceRef);
    await page.getByPlaceholder("银行附言 / 账单号").fill(bill.bill_no);
    await page.getByTestId("receipt-create-btn").click();
    await expect(page.getByTestId("receipt-success")).toContainText("尚未形成收款或核销");

    const receiptsResponse = await apiJson(request, "get", "/receipts?page=1&page_size=100", {
      token,
    });
    const receipt = (
      receiptsResponse.body as {
        data: { items: Array<{ id: number; source_ref: string; status: string }> };
      }
    ).data.items.find((item) => item.source_ref === sourceRef);
    expect(receipt?.status).toBe("PENDING");
    await page.locator(`[data-testid=receipt-row-${receipt!.id}]`).getByTestId("receipt-review-btn").click();
    await page.getByTestId("receipt-match-btn").click();
    await expect(page.getByTestId("receipt-review-drawer")).toContainText("EXACT_BILL_REFERENCE");

    const afterSuggestion = await apiJson(request, "get", `/receipts/${receipt!.id}`, { token });
    expect((afterSuggestion.body as { data: { status: string; payment_id: number | null } }).data).toMatchObject({
      status: "SUGGESTED",
      payment_id: null,
    });
    await page.getByTestId("receipt-confirm-btn").click();
    await expect(page.getByTestId("receipt-success")).toContainText("收款与核销结果已落库");

    const confirmed = await apiJson(request, "get", `/receipts/${receipt!.id}`, { token });
    const paymentId = (confirmed.body as { data: { status: string; payment_id: number } }).data.payment_id;
    expect((confirmed.body as { data: { status: string } }).data.status).toBe("CONFIRMED");
    const payment = await apiJson(request, "get", `/payments/${paymentId}`, { token });
    expect((payment.body as { data: { allocated_amount: string; unapplied_amount: string } }).data).toMatchObject({
      allocated_amount: "100.00",
      unapplied_amount: "50.00",
    });

    const nextBillResponse = await apiJson(request, "post", "/bills", {
      token,
      data: {
        park_id: parkId,
        party_id: partyId,
        period_start: "2099-02-01",
        period_end: "2099-02-28",
        due_date: "2099-03-05",
        lines: [{ fee_code: "SERVICE", quantity: "1", unit_price: "50" }],
      },
    });
    const nextBillId = (nextBillResponse.body as { data: { id: number } }).data.id;
    await apiJson(request, "post", `/bills/${nextBillId}/issue`, { token });

    await page.goto("/payments");
    await page.locator(`[data-testid=pay-row-${paymentId}]`).getByTestId("payment-detail-btn").click();
    await page.getByTestId("allocation-bill-id").fill(String(nextBillId));
    await page.getByTestId("allocation-amount").fill("50");
    await page.getByTestId("payment-allocate-btn").click();
    await expect(page.getByTestId("pay-success")).toContainText("未分配余额已核销");
    await expect(page.getByTestId("payment-allocation-drawer")).toContainText("0.00");

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: path.join(evidenceDir, "pc-desktop-payment-allocation.png"), fullPage: true });
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/receipts");
    await page.screenshot({ path: path.join(evidenceDir, "pc-tablet-receipt-inbox.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileRow = page.locator(`[data-testid=receipt-row-${receipt!.id}]`);
    await expect(mobileRow).toContainText("¥ 150.00");
    const tableMetrics = await page.getByTestId("receipt-table").evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(tableMetrics.scrollWidth).toBeLessThanOrEqual(tableMetrics.clientWidth + 1);
    const bodyMetrics = await page.locator("body").evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(bodyMetrics.scrollWidth).toBeLessThanOrEqual(bodyMetrics.clientWidth + 1);
    await page.screenshot({ path: path.join(evidenceDir, "pc-mobile-receipt-inbox.png"), fullPage: true });
  });

  test("aging preview creates one L4 case and records provider truth", async ({ page, request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = (
      await apiJson(request, "post", "/parks", {
        token,
        data: { name: uniqueName("DunningPark"), address: "dunning-e2e" },
      })
    ).body as { data: { id: number } };
    const party = (
      await apiJson(request, "post", "/parties", {
        token,
        data: { name: uniqueName("DunningParty"), party_type: "ORGANIZATION" },
      })
    ).body as { data: { id: number } };
    const billResponse = await apiJson(request, "post", "/bills", {
        token,
        data: {
          park_id: park.data.id,
          party_id: party.data.id,
          period_start: "2098-12-01",
          period_end: "2098-12-31",
          due_date: "2099-01-01",
          lines: [{ fee_code: "MANAGEMENT", quantity: "1", unit_price: "360" }],
        },
      });
    expect(billResponse.status).toBe(200);
    const bill = billResponse.body as { data: { id: number } };
    await apiJson(request, "post", `/bills/${bill.data.id}/issue`, { token });

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/collection");
    await page.getByLabel("账龄截止日").fill("2099-03-05");
    await page.getByPlaceholder("园区 ID（可空）").fill(String(park.data.id));
    await page.getByTestId("dunning-preview-btn").click();
    await expect(page.getByTestId("dunning-preview-result")).toContainText("欠费 1 笔");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByTestId("dunning-apply-btn").click();
    await expect(page.getByTestId("collection-success")).toContainText("没有伪造发送");
    const cases = await apiJson(request, "get", `/collection/cases?bill_id=${bill.data.id}`, {
      token,
    });
    const caseItem = (cases.body as { data: { items: Array<{ id: number; level: string }> } }).data.items[0];
    expect(caseItem.level).toBe("L4");
    await page.locator(`[data-testid=collection-row-${caseItem.id}]`).getByTestId("collection-history-btn").click();
    await expect(page.getByTestId("collection-history-drawer")).toContainText("PLANNED");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: path.join(evidenceDir, "pc-desktop-collection-aging.png"), fullPage: true });
  });
});
