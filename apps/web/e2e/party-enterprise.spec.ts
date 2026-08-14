import { test, expect, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  ADMIN_PASS,
  ADMIN_USER,
  LIMITED_PASS,
  LIMITED_USER,
  apiJson,
  apiLogin,
  loginAs,
  requireApiHealthy,
  uniqueName,
} from "./helpers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EVIDENCE_DIR = path.resolve(
  __dirname,
  "../../../docs/06-implementation/evidence/party-enterprise-profile"
);
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

type Envelope<T> = { data: T };

function dataOf<T>(body: unknown): T {
  return (body as Envelope<T>).data;
}

async function seedEnterprise(request: APIRequestContext) {
  const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
  const suffix = uniqueName("企业画像").replace(/-/g, "").slice(-10).toUpperCase();
  const creditCode = `91310000${suffix.slice(-8)}AB`;
  const created = await apiJson(request, "post", "/parties", {
    token,
    data: {
      name: `浏览器企业画像${suffix}`,
      party_type: "ORGANIZATION",
      credit_code: creditCode,
    },
  });
  expect(created.status).toBe(200);
  const party = dataOf<{ id: number; name: string }>(created.body);
  const profile = await apiJson(
    request,
    "put",
    `/parties/${party.id}/enterprise-profile`,
    {
      token,
      data: {
        expected_lock_version: 0,
        short_name: `浏览器画像${suffix.slice(-4)}`,
        legal_representative: "合成负责人",
        established_on: "2020-01-02",
        registered_capital: "800000.00",
        capital_currency: "CNY",
        registration_status: "ACTIVE",
        industry_code: "I65",
        industry_name: "软件和信息技术服务业",
        business_scope: "浏览器验收合成数据",
      },
    }
  );
  expect(profile.status).toBe(200);
  return { token, party, suffix };
}

test.describe("enterprise Party workspace", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("desktop directory, profile mutation and conflict-preserving drawer", async ({
    page,
    request,
  }) => {
    const seeded = await seedEnterprise(request);
    const related = await seedEnterprise(request);
    await page.setViewportSize({ width: 1440, height: 960 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/parties");
    await expect(page.getByTestId("parties-title")).toBeVisible();
    await page.getByTestId("party-keyword").fill(seeded.suffix);
    await page.getByTestId("enterprise-registration-filter").selectOption("ACTIVE");
    await page.getByTestId("party-filter-btn").click();
    const row = page.getByTestId(`party-row-${seeded.party.id}`);
    await expect(row).toContainText(seeded.party.name);
    await row.getByRole("button", { name: "打开画像" }).click();
    const drawer = page.getByTestId("enterprise-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("NOT_CONNECTED");
    await expect(drawer).toContainText("本地风险");
    await drawer.getByLabel("企业简称").fill(`已修改${seeded.suffix.slice(-4)}`);
    await page.getByTestId("enterprise-profile-save").click();
    await expect(page.getByTestId("party-success")).toContainText("画像已保存");

    const relationshipSection = page.getByTestId("enterprise-relationship-section");
    await relationshipSection.getByPlaceholder("目标企业 ID").fill(String(related.party.id));
    await relationshipSection.getByRole("button", { name: "新增关系" }).click();
    await expect(relationshipSection).toContainText(related.party.name);

    const tagSection = page.getByTestId("enterprise-tag-section");
    const browserTag = `浏览器资质${seeded.suffix.slice(-4)}`;
    await tagSection.getByPlaceholder("标签名称").fill(browserTag);
    await tagSection.getByRole("button", { name: "新增标签" }).click();
    await expect(tagSection).toContainText(browserTag);

    const riskSection = page.getByTestId("enterprise-risk-section");
    const browserRisk = `浏览器合规核查${seeded.suffix.slice(-4)}`;
    await riskSection.getByPlaceholder("风险摘要").fill(browserRisk);
    await riskSection.getByRole("button", { name: "记录风险" }).click();
    await expect(riskSection).toContainText(browserRisk);
    await riskSection.getByRole("button", { name: "标记已缓释" }).click();
    await expect(riskSection).toContainText("已处置");

    const credentialSection = page.getByTestId("enterprise-credential-section");
    await credentialSection
      .getByPlaceholder("组织证照标识（仅保存指纹和掩码）")
      .fill(`91310000${seeded.suffix}AB`);
    await credentialSection.getByPlaceholder("签发机构").fill("浏览器合成登记机构");
    await credentialSection.locator('input[type="file"]').setInputFiles({
      name: `license-${seeded.suffix}.txt`,
      mimeType: "text/plain",
      buffer: Buffer.from("synthetic browser business-license evidence"),
    });
    await credentialSection.getByRole("button", { name: "上传证照证据" }).click();
    await expect(credentialSection).toContainText("BUSINESS_LICENSE");
    await expect(credentialSection).toContainText("****");

    let conflictInjected = false;
    await page.route(`**/api/v1/parties/${seeded.party.id}/enterprise-profile`, async (route) => {
      if (route.request().method() === "PUT" && !conflictInjected) {
        conflictInjected = true;
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            code: "ENTERPRISE_PROFILE_CONFLICT",
            message: "企业画像版本冲突",
            data: null,
          }),
        });
        return;
      }
      await route.continue();
    });
    const retainedDraft = `冲突草稿${seeded.suffix.slice(-4)}`;
    await drawer.getByLabel("企业简称").fill(retainedDraft);
    await page.getByTestId("enterprise-profile-save").click();
    await expect(drawer).toContainText("版本冲突，草稿已保留");
    await expect(drawer.getByLabel("企业简称")).toHaveValue(retainedDraft);
    await page.unroute(`**/api/v1/parties/${seeded.party.id}/enterprise-profile`);
    await drawer.evaluate((element) => {
      element.scrollTop = 0;
    });
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-enterprise-conflict.png"),
    });
    expect(
      await page.evaluate(
        () => document.body.scrollWidth <= document.documentElement.clientWidth
      )
    ).toBe(true);
  });

  test("tablet read-only user never fetches or renders credential metadata", async ({
    page,
    request,
  }) => {
    const seeded = await seedEnterprise(request);
    let credentialRequests = 0;
    await page.route("**/api/v1/parties/*/enterprise-credentials**", async (route) => {
      credentialRequests += 1;
      await route.continue();
    });
    await page.setViewportSize({ width: 820, height: 1050 });
    await loginAs(page, LIMITED_USER, LIMITED_PASS);
    await page.goto("/parties");
    await page.getByTestId("party-keyword").fill(seeded.suffix);
    await page.getByTestId("party-filter-btn").click();
    await page.getByTestId(`enterprise-open-${seeded.party.id}`).click();
    const drawer = page.getByTestId("enterprise-drawer");
    await expect(drawer).toContainText("没有企业证照读取权限");
    await expect(drawer).toContainText("没有企业风险读取权限");
    expect(credentialRequests).toBe(0);
    expect(
      await page.evaluate(
        () => document.body.scrollWidth <= document.documentElement.clientWidth
      )
    ).toBe(true);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-tablet-enterprise-readonly.png"),
    });
  });

  test("mobile directory exposes offline error and recovers through retry", async ({
    page,
    request,
  }) => {
    const seeded = await seedEnterprise(request);
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/parties");
    await expect(page.getByTestId("party-table")).toBeVisible();
    const pattern = "**/api/v1/enterprise-parties**";
    await page.route(pattern, async (route) => route.abort("internetdisconnected"));
    await page.getByTestId("party-keyword").fill(seeded.suffix);
    await page.getByTestId("party-filter-btn").click();
    await expect(page.getByTestId("party-error")).toContainText("网络不可用");
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-mobile-enterprise-offline.png"),
      fullPage: true,
    });
    await page.unroute(pattern);
    await page.getByTestId("party-retry").click();
    await expect(page.getByTestId(`party-row-${seeded.party.id}`)).toBeVisible();
    await page.getByTestId(`enterprise-open-${seeded.party.id}`).click();
    await expect(page.getByTestId("enterprise-drawer")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.body.scrollWidth <= document.documentElement.clientWidth
      )
    ).toBe(true);
  });
});
