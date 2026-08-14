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
  "../../../docs/06-implementation/evidence/workforce-scheduling-attendance-performance"
);

function dataOf<T>(body: unknown): T {
  return (body as { data: T }).data;
}

test.describe("workforce scheduling attendance performance qualification", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("real workforce UI journey, responsive layout and offline recovery", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/parks", {
          token,
          data: { name: uniqueName("WorkforcePark"), address: "workforce-e2e" },
        })
      ).body
    );
    const suffix = uniqueName("wf").replace(/-/g, "").slice(-8).toUpperCase();
    const employeeNo = `EMP_${suffix}`;
    const shiftCode = `DAY_${suffix}`;
    const locationCode = `GATE_${suffix}`;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/workforce");
    await expect(page.getByTestId("workforce-title")).toBeVisible();
    await expect(page.getByText("设备接入")).toBeVisible();
    await expect(page.getByText("NOT_CONNECTED").first()).toBeVisible();

    await page.getByTestId("add-workforce-employee").click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("员工编号").fill(employeeNo);
    await page.getByLabel("姓名").fill("E2E 现场员工");
    await page.getByLabel("部门").fill("物业运营");
    await page.getByLabel("岗位").fill("巡检专员");
    await page.getByRole("button", { name: "建立员工档案" }).click();
    await expect(page.getByTestId("workforce-success")).toContainText("员工已建立受控档案");
    await expect(page.getByTestId("workforce-employee-table")).toContainText(employeeNo);

    await page.getByRole("button", { name: "班次排班" }).click();
    await page.getByRole("button", { name: "发布班次" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("编码").fill(shiftCode);
    await page.getByLabel("名称").fill("E2E 日班");
    await page.getByRole("button", { name: "发布版本 1" }).click();
    await expect(page.getByText("班次版本已发布")).toBeVisible();
    await page.getByLabel("员工").selectOption({ label: `${employeeNo} · E2E 现场员工` });
    await page.getByLabel("班次版本").selectOption({ label: `${shiftCode} · v1` });
    await page.getByRole("button", { name: "校验并排班" }).click();
    await expect(page.getByText("排班已保存并完成冲突校验")).toBeVisible();

    await page.getByRole("button", { name: "考勤请假" }).click();
    await page.getByRole("button", { name: "登记地点" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("地点编码").fill(locationCode);
    await page.getByLabel("地点名称").fill("E2E 东门");
    await page.getByLabel("加密配置引用").fill(`secret://attendance/${locationCode}`);
    await page.getByRole("button", { name: "登记引用" }).click();
    await expect(page.getByText("数据库不保存精确坐标")).toBeVisible();
    await page.getByLabel("员工").first().selectOption({ label: `${employeeNo} · E2E 现场员工` });
    await page.getByLabel("地点").selectOption({ label: `${locationCode} · E2E 东门` });
    await page.getByLabel("距离（米）").fill("40");
    await page.getByLabel("设备标识").fill("e2e-mobile-device");
    await page.getByRole("button", { name: "记录打卡" }).click();
    await expect(page.getByText("精确坐标未持久化")).toBeVisible();
    await page.getByLabel("员工").last().selectOption({ label: `${employeeNo} · E2E 现场员工` });
    await page.getByRole("button", { name: "重新计算" }).click();
    await expect(page.getByText("考勤汇总已重新计算")).toBeVisible();
    await expect(page.getByTestId("attendance-summary-table")).toContainText("MISSING_OUT");

    await page.getByRole("button", { name: "绩效评价" }).click();
    await page.getByRole("button", { name: "新建周期" }).click();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("周期编码").fill(`CYCLE_${suffix}`);
    await page.getByLabel("周期名称").fill("E2E 月度履职");
    await page.getByRole("button", { name: "创建草稿周期" }).click();
    await expect(page.getByText("绩效周期已创建")).toBeVisible();

    await page.getByRole("button", { name: "员工资质" }).click();
    await page.getByRole("button", { name: "维护资质" }).click();
    await page.getByLabel("类型编码").fill(`ELECTRIC_${suffix}`);
    await page.getByLabel("类型名称").fill("E2E 电工作业证");
    await page.getByRole("button", { name: "保存类型" }).click();
    await expect(page.getByText("资质类型已创建")).toBeVisible();

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "pc-desktop-workforce-qualification.png"),
      fullPage: false,
    });
    await page.setViewportSize({ width: 820, height: 1180 });
    await page.getByRole("button", { name: "考勤请假" }).click();
    await page.screenshot({
      path: path.join(evidenceDir, "pc-tablet-workforce-attendance.png"),
      fullPage: true,
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/v1/workforce/**", (route) => route.abort("failed"));
    await page.getByTestId("workforce-refresh").click();
    await expect(page.getByTestId("workforce-error")).toBeVisible();
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
      path: path.join(evidenceDir, "pc-mobile-workforce-offline-retry.png"),
      fullPage: true,
    });
  });
});
