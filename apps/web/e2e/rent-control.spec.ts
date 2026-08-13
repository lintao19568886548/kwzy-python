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

    await loginAs(page, "e2e_limited", "limited123");
    await page.goto("/rent-control");
    await expect(page.getByTestId("forbidden-page")).toBeVisible();

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.route("**/api/v1/rent-control/summary**", (route) =>
      route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "TEMPORARY_FAILURE", message: "租控汇总暂不可用", data: null }) })
    );
    await page.goto("/rent-control");
    await expect(page.getByTestId("rent-error")).toContainText("租控汇总暂不可用");
  });

  test("tablet view keeps core controls keyboard reachable", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/rent-control");
    await expect(page.getByTestId("rent-control-title")).toBeVisible();
    await page.getByTestId("view-matrix").focus();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("view-list")).toBeFocused();
    await page.getByTestId("rent-park-select").focus();
    await expect(page.getByTestId("rent-park-select")).toBeFocused();
  });
});
