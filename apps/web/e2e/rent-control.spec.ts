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
const EVIDENCE_DIR = path.resolve(
  __dirname,
  "../../../docs/06-implementation/evidence/platform-asset-portfolio-views"
);
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

test.describe("asset rent control", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
  });

  test("authorized park, hierarchy, matrix, detail, split and merge primary path", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const parkName = uniqueName("租控验收园");
    const parkResult = await apiJson(request, "post", "/parks", {
      token,
      data: { name: parkName, address: "E2E asset road" },
    });
    expect(parkResult.status).toBe(200);

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/rent-control");
    await expect(page.getByTestId("rent-control-title")).toBeVisible();
    await page.getByTestId("rent-park-select").selectOption({ label: parkName });
    await expect(page.getByTestId("rent-empty")).toBeVisible();

    const buildingCode = uniqueName("B").replace(/-/g, "").slice(-14).toUpperCase();
    const buildingName = `验收楼栋${buildingCode.slice(-4)}`;
    await page.getByTestId("space-create-open").click();
    await page.getByTestId("space-type").selectOption("BUILDING");
    await page.getByTestId("space-code").fill(buildingCode);
    await page.getByTestId("space-name").fill(buildingName);
    await page.getByTestId("space-save").click();
    await expect(page.getByTestId("rent-success")).toContainText("空间节点已创建");
    const buildingNode = page.getByRole("button", { name: new RegExp(buildingName) });
    await expect(buildingNode).toBeVisible();
    await buildingNode.click();

    const codeBase = uniqueName("U").replace(/-/g, "").slice(-10).toUpperCase();
    const firstCode = `${codeBase}A`;
    const secondCode = `${codeBase}B`;
    for (const [code, name, area] of [
      [firstCode, "可拆分单元", "100"],
      [secondCode, "合并候选单元", "40"],
    ]) {
      await page.getByTestId("unit-create-open").click();
      await page.getByTestId("unit-code-v2").fill(code);
      await page.getByTestId("unit-name-v2").fill(name);
      await page.getByTestId("unit-area-v2").fill(area);
      await page.getByTestId("unit-save-v2").click();
      await expect(page.getByTestId("rent-success")).toContainText("出租单元已创建");
    }

    await expect(page.getByTestId("rent-summary")).toContainText("140");
    await expect(page.getByTestId("rent-matrix")).toContainText(firstCode);
    await page.getByRole("button", { name: new RegExp(firstCode) }).click();
    await expect(page.getByTestId("rent-detail")).toContainText("锁版本 1");
    await page.getByTestId("unit-split-open").click();
    await page.getByTestId("unit-split-save").click();
    await expect(page.getByTestId("rent-success")).toContainText("原子拆分");
    await expect(page.getByTestId("rent-matrix")).toContainText(`${firstCode}-A`);

    await page.getByRole("button", { name: new RegExp(`${firstCode}-A`) }).click();
    await expect(page.getByTestId("unit-merge-open")).toBeEnabled();
    await page.getByTestId("unit-merge-open").click();
    await page.getByTestId("unit-merge-save").click();
    await expect(page.getByTestId("rent-success")).toContainText("原子合并");
    await expect(page.getByTestId("rent-detail")).toContainText("MERGE");

    await page.getByTestId("view-list").click();
    await expect(page.getByTestId("rent-list")).toBeVisible();
    await page.getByTestId("rent-keyword").fill(secondCode);
    await page.getByTestId("rent-filter-submit").click();
    await expect(page.getByTestId("rent-list")).toContainText(secondCode);
  });

  test("read-only controls, denied route and failure state are explicit", async ({ page }) => {
    await loginAs(page, "e2e_asset_viewer", "viewer123");
    await page.goto("/rent-control");
    await expect(page.getByTestId("rent-control-title")).toBeVisible();
    await expect(page.getByTestId("space-create-open")).toHaveCount(0);
    await expect(page.getByTestId("unit-create-open")).toHaveCount(0);
    await page.getByTestId("asset-template-toggle").click();
    await expect(page.getByTestId("asset-template-panel")).toContainText("OFFICE");
    await expect(page.getByTestId("asset-template-create")).toHaveCount(0);

    await loginAs(page, "e2e_limited", "limited123");
    await page.goto("/rent-control");
    await expect(page.getByTestId("forbidden-page")).toBeVisible();

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.route("**/api/v1/rent-control/summary**", (route) =>
      route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "TEMPORARY_FAILURE", message: "租控汇总暂不可用", data: null }) })
    );
    await page.goto("/rent-control");
    await expect(page.getByTestId("rent-error")).toContainText("租控汇总暂不可用");
    await expect(page.getByTestId("rent-retry")).toBeVisible();
  });

  test("versioned template, real geometry map, vacancy, expiry and analysis views", async ({ page, request }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const parkName = uniqueName("多视图验收园");
    const parkResult = await apiJson(request, "post", "/parks", {
      token,
      data: { name: parkName, address: "asset portfolio e2e" },
    });
    expect(parkResult.status).toBe(200);
    const parkId = (parkResult.body as { data: { id: number } }).data.id;
    const spaceCode = uniqueName("MAP").replace(/-/g, "").slice(-14).toUpperCase();
    const spaceName = `地图楼栋${spaceCode.slice(-4)}`;
    const spaceResult = await apiJson(request, "post", "/spaces", {
      token,
      data: {
        park_id: parkId,
        code: spaceCode,
        name: spaceName,
        node_type: "BUILDING",
        geometry: {
          type: "Polygon",
          coordinates: [[[10, 10], [210, 10], [210, 130], [10, 130], [10, 10]]],
        },
        coordinate_reference: "LOCAL",
      },
    });
    expect(spaceResult.status).toBe(200);
    const spaceId = (spaceResult.body as { data: { id: number } }).data.id;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/rent-control");
    await page.getByTestId("rent-park-select").selectOption({ label: parkName });
    await page.getByTestId("asset-template-toggle").click();
    await expect(page.getByTestId("asset-template-OFFICE")).toBeVisible();

    const templateCode = uniqueName("OFFICEE2E").replace(/-/g, "").slice(-20).toUpperCase();
    const templateName = `验收办公模板${templateCode.slice(-4)}`;
    await page.getByTestId("asset-template-create").click();
    await page.getByTestId("asset-template-code").fill(templateCode);
    await page.getByTestId("asset-template-name").fill(templateName);
    await page.getByTestId("asset-template-category").selectOption("OFFICE");
    await page.getByTestId("asset-template-fields").fill(
      JSON.stringify([{ key: "capacity", label: "容量", type: "NUMBER", required: true }])
    );
    await page.getByTestId("asset-template-save").click();
    await expect(page.getByTestId("rent-success")).toContainText("模板草稿已创建");
    const templateCard = page.getByTestId(`asset-template-${templateCode}`);
    await expect(templateCard).toBeVisible();
    await templateCard.getByRole("button", { name: "发布" }).click();
    await expect(page.getByTestId("rent-success")).toContainText("模板已发布");

    const unitCode = uniqueName("OFFICE").replace(/-/g, "").slice(-16).toUpperCase();
    await page.getByTestId("unit-create-open").click();
    await page.getByTestId("unit-space").selectOption(String(spaceId));
    await page.getByTestId("unit-template").selectOption({ label: `${templateName} · V1` });
    await page.getByTestId("unit-code-v2").fill(unitCode);
    await page.getByTestId("unit-name-v2").fill("模板绑定办公单元");
    await page.getByTestId("unit-area-v2").fill("88");
    await page.getByTestId("unit-base-rent-v2").fill("10");
    await page.getByTestId("unit-attribute-capacity").fill("12");
    await page.getByTestId("unit-save-v2").click();
    await expect(page.getByTestId("rent-success")).toContainText("出租单元已创建");

    await page.getByTestId("view-map").click();
    await expect(page.getByTestId("rent-map")).toContainText(spaceName);
    await expect(page.getByTestId("rent-map")).toContainText("坐标参考 LOCAL");
    await expect(page.getByTestId("rent-map")).toContainText("外部底图未接入");
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-rent-control-map.png"),
      fullPage: true,
    });
    await page.getByTestId("view-vacancy").click();
    await expect(page.getByTestId("rent-vacancies")).toContainText(unitCode);
    await expect(page.getByTestId("rent-vacancies")).toContainText("88");
    await page.getByTestId("view-expiry").click();
    await expect(page.getByTestId("rent-expiries")).toContainText("180 天内无到期占用");
    await page.getByTestId("view-analysis").click();
    await expect(page.getByTestId("rent-analysis")).toContainText("OFFICE");
    await expect(page.getByTestId("rent-analysis")).toContainText("非会计收入");
    await expect(page.getByTestId("rent-analysis")).toContainText("¥ 880.00");
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-rent-control-analysis.png"),
      fullPage: true,
    });

    await page.getByTestId("view-matrix").click();
    await page.getByRole("button", { name: new RegExp(unitCode) }).click();
    await expect(page.getByTestId("rent-detail")).toContainText(templateName);
    await expect(page.getByTestId("rent-detail")).toContainText(`${templateCode} · V1`);
  });

  test("mobile offline state blocks stale-data claims and retries after recovery", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/rent-control");
    const activeNav = page.getByTestId("nav-rent-control");
    const nav = page.getByTestId("main-nav");
    await expect(activeNav).toBeVisible();
    await expect
      .poll(async () => {
        const [activeBox, navBox] = await Promise.all([activeNav.boundingBox(), nav.boundingBox()]);
        if (!activeBox || !navBox) return false;
        return activeBox.x >= navBox.x && activeBox.x + activeBox.width <= navBox.x + navBox.width;
      })
      .toBe(true);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.context().setOffline(true);
    await expect(page.getByTestId("rent-error")).toContainText("网络已断开");
    await expect(page.getByTestId("rent-retry")).toBeDisabled();
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-mobile-rent-control-offline.png"),
      fullPage: true,
    });
    await page.context().setOffline(false);
    await expect(page.getByTestId("rent-retry")).toBeEnabled();
    await page.getByTestId("rent-retry").click();
    await expect(page.getByTestId("rent-control-title")).toBeVisible();
    await expect(page.getByTestId("rent-error")).toHaveCount(0);
  });

  test("tablet view keeps core controls keyboard reachable", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/rent-control");
    await expect(page.getByTestId("rent-control-title")).toBeVisible();
    await page.getByTestId("view-matrix").focus();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("view-map")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("view-list")).toBeFocused();
    await page.getByTestId("rent-park-select").focus();
    await expect(page.getByTestId("rent-park-select")).toBeFocused();
  });
});
