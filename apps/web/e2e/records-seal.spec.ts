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
  "../../../docs/06-implementation/evidence/records-signature-seal-governance"
);

function dataOf<T>(body: unknown): T {
  return (body as { data: T }).data;
}

test.describe("records, signature and seal governance", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("real attachment record, custody register and truthful sandbox signature", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/parks", {
          token,
          data: { name: uniqueName("RecordsPark"), address: "records-seal-e2e" },
        })
      ).body
    );
    const suffix = uniqueName("record").replace(/-/g, "").slice(-12).toUpperCase();
    const categoryCode = `E2E_${suffix}`;
    const sourceId = `LEASE:${suffix}`;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/records-seal");
    await expect(page.getByTestId("records-seal-title")).toBeVisible();
    await page.getByTestId("add-record-category").click();
    await page.getByLabel("分类编码").fill(categoryCode);
    await page.getByLabel("分类名称").fill("E2E 合同档案");
    await page.getByLabel("保管年限").fill("10");
    await page.getByRole("button", { name: "保存分类" }).click();
    await expect(page.getByText("档案分类已保存")).toBeVisible();

    await page.getByTestId("add-record").click();
    await page.getByLabel("园区 ID（集团档案可留空）").fill(String(park.id));
    await page.getByLabel("档案分类").selectOption({ label: `${categoryCode} · E2E 合同档案` });
    await page.getByLabel("标题").fill("E2E 主合同归档件");
    await page.getByLabel("密级").selectOption("CONFIDENTIAL");
    await page.getByLabel("来源业务 ID").fill(sourceId);
    await page.getByRole("button", { name: "创建受控档案" }).click();
    await expect(page.getByText("档案已创建，可绑定真实附件版本")).toBeVisible();

    const content = Buffer.from(`governed-e2e-${suffix}`, "utf8");
    const attachment = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/attachments", {
          token,
          data: {
            biz_type: "RECORD_SOURCE",
            biz_id: suffix,
            filename: "e2e-contract.txt",
            content_type: "text/plain",
            content_base64: content.toString("base64"),
            park_id: park.id,
          },
        })
      ).body
    );
    await page.getByLabel("已上传附件 ID").fill(String(attachment.id));
    await page.getByRole("button", { name: "生成新版本" }).click();
    await expect(page.getByText("真实附件已哈希并生成不可变档案版本")).toBeVisible();
    await expect(page.getByRole("complementary", { name: "档案详情", exact: true })).toContainText(
      "修订 1"
    );
    await page.getByRole("button", { name: "正式归档" }).click();
    await expect(page.getByText("档案已正式归档")).toBeVisible();
    await page.getByRole("button", { name: "校验完整性" }).click();
    await expect(page.getByText("档案对象与 SHA-256 校验值一致")).toBeVisible();
    await expect(page.getByRole("complementary", { name: "档案详情", exact: true })).toContainText(
      "MATCH"
    );
    await page.getByRole("button", { name: "关闭档案详情" }).click();

    const records = dataOf<{ items: Array<{ id: number; source_id: string }> }>(
      (await apiJson(request, "get", "/records?page=1&page_size=200", { token })).body
    );
    const record = records.items.find((item) => item.source_id === sourceId)!;
    const recordDetail = dataOf<{ revisions: Array<{ id: number }> }>(
      (await apiJson(request, "get", `/records/${record.id}`, { token })).body
    );

    await page.getByRole("button", { name: "印章与用印" }).click();
    await page.getByTestId("add-seal").click();
    const sealCode = `SEAL_${suffix}`;
    await page.getByLabel("园区 ID（集团章可留空）").fill(String(park.id));
    await page.getByLabel("印章编码").fill(sealCode);
    await page.getByLabel("印章名称").fill("E2E 合同专用章");
    await page.getByLabel("类型").selectOption("CONTRACT");
    await page.getByLabel("保管人用户 ID").fill("1");
    await page.getByRole("button", { name: "登记并建立保管链" }).click();
    await expect(page.getByText("印章已登记并生成首条保管事件")).toBeVisible();
    await page.getByRole("button", { name: `查看印章 ${sealCode}` }).click();
    await expect(page.getByRole("complementary", { name: "印章详情", exact: true })).toContainText(
      "CREATED · COMPLETED"
    );
    await page.getByRole("button", { name: "关闭印章详情" }).click();

    await page.getByRole("button", { name: "电子签章" }).click();
    await page.getByTestId("add-signature-provider").click();
    const providerCode = `SIG_${suffix}`;
    await page.getByLabel("服务编码").fill(providerCode);
    await page.getByLabel("服务名称").fill("E2E 无法律效力沙箱");
    await page.getByRole("button", { name: "登记真实状态" }).click();
    await expect(page.getByText("本地签章沙箱已登记：无法律效力")).toBeVisible();
    await expect(
      page.getByRole("article").filter({ hasText: providerCode }).getByText("仅本地流程模拟 · 无法律效力")
    ).toBeVisible();
    const provider = dataOf<Array<{ id: number; code: string }>>(
      (await apiJson(request, "get", "/signature-providers", { token })).body
    ).find((item) => item.code === providerCode)!;

    await page.getByTestId("add-signature-envelope").click();
    await page.getByLabel("签章服务").selectOption(String(provider.id));
    await page.getByLabel("档案 ID").fill(String(record.id));
    await page.getByLabel("档案版本 ID").fill(String(recordDetail.revisions[0].id));
    await page.getByLabel("来源业务 ID").fill(sourceId);
    await page.getByLabel("用途").fill("E2E 合同签署流程验证");
    await page.getByLabel("签署人").fill("验收签署人");
    await page.getByLabel("脱敏联系方式").fill("138****8000");
    await page.getByRole("button", { name: "绑定最新版本" }).click();
    await expect(page.getByText("签署信封已绑定档案最新版本")).toBeVisible();
    await page
      .getByTestId("signature-envelope-table")
      .getByRole("row")
      .filter({ hasText: "E2E 合同签署流程验证" })
      .getByRole("button", { name: "发送" })
      .click();
    await expect(page.getByText("签署流程已处理；沙箱结果不具法律效力")).toBeVisible();
    await expect(page.getByTestId("signature-envelope-table")).toContainText("SANDBOX_COMPLETED");

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "pc-desktop-signature-truth.png"),
      fullPage: false,
    });
    await page.setViewportSize({ width: 820, height: 1180 });
    await page.screenshot({
      path: path.join(evidenceDir, "pc-tablet-signature-truth.png"),
      fullPage: true,
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "档案库" }).click();
    await page.route("**/api/v1/records**", (route) => route.abort("failed"));
    await page.getByRole("button", { name: "刷新真实数据" }).click();
    await expect(page.getByTestId("records-error")).toContainText("网络或服务异常");
    const bodySize = await page.locator("body").evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(bodySize.scrollWidth).toBeLessThanOrEqual(bodySize.clientWidth + 1);
    const mobileLayout = await page.evaluate(() => {
      const viewportWidth = document.documentElement.clientWidth;
      const tabRects = Array.from(document.querySelectorAll<HTMLElement>(".tabs button")).map((element) =>
        element.getBoundingClientRect()
      );
      const tableWrap = document.querySelector<HTMLElement>("[data-testid='record-table']")?.parentElement;
      return {
        tabsInsideViewport: tabRects.every((rect) => rect.left >= 0 && rect.right <= viewportWidth + 1),
        tableFitsContainer: tableWrap ? tableWrap.scrollWidth <= tableWrap.clientWidth + 1 : false,
      };
    });
    expect(mobileLayout.tabsInsideViewport).toBe(true);
    expect(mobileLayout.tableFitsContainer).toBe(true);
    await page.screenshot({
      path: path.join(evidenceDir, "pc-mobile-records-offline-retry.png"),
      fullPage: true,
    });
  });
});
