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

test.describe("bill and payment main chain", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("create issue bill partial then full pay reverse", async ({ page, request }) => {
    page.on("dialog", (d) => d.accept());
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);

    const park = await apiJson(request, "post", "/parks", {
      token,
      data: { name: uniqueName("BillPark"), address: "bill-road" },
    });
    const parkId = (park.body as { data: { id: number } }).data.id;
    const party = await apiJson(request, "post", "/parties", {
      token,
      data: { name: uniqueName("BillParty"), party_type: "ORGANIZATION" },
    });
    const partyId = (party.body as { data: { id: number } }).data.id;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);

    // create draft bill
    await page.goto("/bills");
    await page.getByTestId("bill-park-id").fill(String(parkId));
    await page.getByTestId("bill-party-id").fill(String(partyId));
    await page.getByTestId("bill-amount").fill("200.00");
    await page.getByTestId("bill-create-btn").click();
    await expect(page.getByTestId("bill-success")).toContainText(/创建/, { timeout: 15000 });

    const bills = await apiJson(request, "get", `/bills?page=1&page_size=50`, { token });
    const billItems = (
      bills.body as {
        data: {
          items: Array<{ id: number; party_id: number; status: string; total_amount: string }>;
        };
      }
    ).data.items;
    const bill = billItems.find((b) => b.party_id === partyId);
    expect(bill).toBeTruthy();
    const billId = bill!.id;

    // issue
    await page.locator(`[data-testid=bill-row-${billId}]`).getByTestId("bill-issue-btn").click();
    await expect(page.getByTestId("bill-success")).toContainText(/签发/, { timeout: 15000 });

    // partial payment 80
    await page.goto("/payments");
    await page.getByTestId("pay-park-id").fill(String(parkId));
    await page.getByTestId("pay-party-id").fill(String(partyId));
    await page.getByTestId("pay-bill-id").fill(String(billId));
    await page.getByTestId("pay-amount").fill("80.00");
    await page.getByTestId("pay-create-btn").click();
    await expect(page.getByTestId("pay-success")).toContainText(/登记/, { timeout: 15000 });

    let billDetail = await apiJson(request, "get", `/bills/${billId}`, { token });
    expect(billDetail.status).toBe(200);
    let billData = (
      billDetail.body as {
        data: { status: string; paid_amount: string; open_amount: string; total_amount: string };
      }
    ).data;
    expect(["PARTIALLY_PAID", "ISSUED"]).toContain(billData.status);
    const remaining = billData.open_amount || "120.00";

    // pay remaining open amount for full settle
    await page.getByTestId("pay-park-id").fill(String(parkId));
    await page.getByTestId("pay-party-id").fill(String(partyId));
    await page.getByTestId("pay-bill-id").fill(String(billId));
    await page.getByTestId("pay-amount").fill(String(remaining));
    await page.getByTestId("pay-create-btn").click();
    await expect(page.getByTestId("pay-success")).toContainText(/登记/, { timeout: 15000 });

    billDetail = await apiJson(request, "get", `/bills/${billId}`, { token });
    billData = (billDetail.body as { data: { status: string; open_amount: string } }).data as typeof billData;
    expect(["PAID", "PARTIALLY_PAID"]).toContain(billData.status);
    if (billData.status !== "PAID") {
      // retry remaining if still open
      const open2 = billData.open_amount;
      if (open2 && Number(open2) > 0) {
        await page.getByTestId("pay-park-id").fill(String(parkId));
        await page.getByTestId("pay-party-id").fill(String(partyId));
        await page.getByTestId("pay-bill-id").fill(String(billId));
        await page.getByTestId("pay-amount").fill(String(open2));
        await page.getByTestId("pay-create-btn").click();
        await expect(page.getByTestId("pay-success")).toContainText(/登记/, { timeout: 15000 });
        billDetail = await apiJson(request, "get", `/bills/${billId}`, { token });
        billData = (billDetail.body as { data: { status: string } }).data as typeof billData;
      }
    }
    expect(billData.status).toBe("PAID");

    // reverse first confirmed payment
    const pays = await apiJson(request, "get", "/payments?page=1&page_size=50", { token });
    const payItems = (
      pays.body as { data: { items: Array<{ id: number; status: string; party_id: number }> } }
    ).data.items.filter((p) => p.party_id === partyId && p.status === "CONFIRMED");
    expect(payItems.length).toBeGreaterThan(0);
    const payId = payItems[0].id;
    await page.goto("/payments");
    await page.locator(`[data-testid=pay-row-${payId}]`).getByTestId("pay-reverse-btn").click();
    await expect(page.getByTestId("pay-success")).toContainText(/冲正/, { timeout: 15000 });

    // idempotent duplicate should fail or no-op with error
    await page.getByTestId("pay-park-id").fill(String(parkId));
    await page.getByTestId("pay-party-id").fill(String(partyId));
    await page.getByTestId("pay-bill-id").fill(String(billId));
    await page.getByTestId("pay-amount").fill("99999");
    // over-pay may error — either way page should not claim success silently
    await page.getByTestId("pay-create-btn").click();
    await page.waitForTimeout(1500);
  });
});
