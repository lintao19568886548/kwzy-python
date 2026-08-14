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
  "../../../docs/06-implementation/evidence/facility-device-inspection-iot"
);

function dataOf<T>(body: unknown): T {
  return (body as { data: T }).data;
}

test.describe("facility operations", () => {
  test.beforeEach(async ({ request }) => {
    await requireApiHealthy(request);
    fs.mkdirSync(evidenceDir, { recursive: true });
  });

  test("device, weekly inspection, alarm work order and responsive recovery", async ({
    page,
    request,
  }) => {
    const token = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const park = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/parks", {
          token,
          data: { name: uniqueName("FacilityPark"), address: "facility-e2e" },
        })
      ).body
    );
    const suffix = uniqueName("inspector").replace(/-/g, "").slice(-10).toLowerCase();
    const role = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/system/roles", {
          token,
          data: {
            code: `FACILITY_INSPECTOR_${suffix}`.toUpperCase(),
            name: `设施巡检员${suffix}`,
            permission_codes: ["inspection:execute"],
            park_ids: [park.id],
            all_parks: false,
          },
        })
      ).body
    );
    const inspectorUser = `facility_${suffix}`;
    const inspectorPassword = "Facility-Inspector!2026";
    const inspector = dataOf<{ id: number }>(
      (
        await apiJson(request, "post", "/system/users", {
          token,
          data: {
            username: inspectorUser,
            password: inspectorPassword,
            real_name: "设施巡检执行人",
            role_ids: [role.id],
            park_ids: [park.id],
            all_parks: false,
          },
        })
      ).body
    );

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/facility-operations");
    await expect(page.getByTestId("facility-title")).toBeVisible();
    await page.getByTestId("facility-add-device").click();
    const deviceCode = `E2E-FIRE-${suffix}`.toUpperCase();
    await page.getByLabel("园区 ID").fill(String(park.id));
    await page.getByLabel("设备编码").fill(deviceCode);
    await page.getByLabel("设备名称").fill("消防泵 E2E");
    await page.getByLabel("位置").fill("A 栋负一层泵房");
    await page.getByLabel("关键等级").selectOption("CRITICAL");
    await page.getByRole("button", { name: "保存设备" }).click();
    await expect(page.getByText("设备已纳入统一台账")).toBeVisible();
    await expect(page.getByTestId("facility-device-table")).toContainText(deviceCode);

    await page.getByRole("button", { name: `查看设备 ${deviceCode}` }).click();
    await page.getByLabel("设备位置").fill("A 栋负一层消防泵房");
    await page.getByLabel("变更原因").fill("E2E 季度维护复核");
    await page.getByRole("button", { name: "保存设备变更" }).click();
    await expect(page.getByText("设备档案已更新并保留版本历史")).toBeVisible();
    await expect(page.getByLabel("设备档案详情")).toContainText("v2 · UPDATED");
    await page.getByRole("button", { name: "关闭设备档案" }).click();

    const deviceList = await apiJson(request, "get", "/facility-devices?page=1&page_size=200", {
      token,
    });
    const device = dataOf<{ items: Array<{ id: number; device_code: string }> }>(
      deviceList.body
    ).items.find((item) => item.device_code === deviceCode)!;

    await page.getByRole("button", { name: "周巡检" }).click();
    await page.getByRole("button", { name: "新建检查模板" }).click();
    const templateCode = `E2E_FIRE_TEMPLATE_${suffix}`.toUpperCase();
    await page.getByLabel("模板编码").fill(templateCode);
    await page.getByLabel("模板名称").fill("消防泵周检 E2E");
    await page.getByLabel("检查项编码").fill("RUNNING");
    await page.getByLabel("检查项名称").fill("运行状态");
    await page.getByRole("button", { name: "创建并发布 v1" }).click();
    await expect(page.getByText("巡检模板已创建并发布")).toBeVisible();

    const templates = dataOf<
      Array<{
        code: string;
        versions: Array<{ id: number; status: string }>;
      }>
    >((await apiJson(request, "get", "/inspection-templates", { token })).body);
    const version = templates
      .find((item) => item.code === templateCode)!
      .versions.find((item) => item.status === "PUBLISHED")!;
    const now = new Date();
    const shanghai = new Date(now.getTime() + 8 * 60 * 60 * 1000 + 30 * 60 * 1000);
    const weekday = shanghai.getUTCDay() === 0 ? 7 : shanghai.getUTCDay();
    const localDueTime = `${String(shanghai.getUTCHours()).padStart(2, "0")}:${String(
      shanghai.getUTCMinutes()
    ).padStart(2, "0")}`;
    await page.getByRole("button", { name: "新建周检计划" }).click();
    const scheduleCode = `E2E-SCHEDULE-${suffix}`.toUpperCase();
    await page.getByLabel("计划园区 ID").fill(String(park.id));
    await page.getByLabel("计划编码").fill(scheduleCode);
    await page.getByLabel("计划名称").fill("消防泵周检计划 E2E");
    await page.getByLabel("计划设备 ID").fill(String(device.id));
    await page.getByLabel("模板版本 ID").fill(String(version.id));
    await page.getByLabel("执行人用户 ID").fill(String(inspector.id));
    await page.getByLabel("周几").selectOption(String(weekday));
    await page.getByLabel("当地截止时间").fill(localDueTime);
    await page.getByLabel("完成窗口（分钟）").fill("10080");
    await page.getByRole("button", { name: "保存周检计划" }).click();
    await expect(page.getByText("周巡检计划已创建")).toBeVisible();
    const scheduleCard = page.getByRole("article").filter({ hasText: scheduleCode });
    await scheduleCard.getByRole("button", { name: "暂停计划" }).click();
    await expect(page.getByText("巡检计划已暂停")).toBeVisible();
    await scheduleCard.getByRole("button", { name: "恢复计划" }).click();
    await expect(page.getByText("巡检计划已恢复")).toBeVisible();
    await page.getByRole("button", { name: "生成本周任务" }).click();
    await expect(page.getByText("本周巡检任务已幂等生成")).toBeVisible();
    const taskList = dataOf<{ items: Array<{ id: number; device_id: number }> }>(
      (await apiJson(request, "get", "/inspection-tasks?page=1&page_size=200", { token })).body
    );
    const taskId = taskList.items.find((item) => item.device_id === device.id)!.id;

    await loginAs(page, inspectorUser, inspectorPassword);
    await page.goto("/facility-operations");
    await page.getByRole("button", { name: "周巡检" }).click();
    await page.getByTestId(`inspection-task-${taskId}`).click();
    await page.getByRole("button", { name: "开始巡检" }).click();
    await expect(page.getByText("巡检任务已开始")).toBeVisible();
    await page.getByRole("combobox").selectOption({ label: "不通过" });
    await page.getByPlaceholder("异常说明").fill("消防泵无法启动，已拍摄现场证据");
    await page.getByRole("button", { name: "提交全部检查结果" }).click();
    await expect(page.getByText("巡检结果已提交")).toBeVisible();
    await expect(page.getByRole("link", { name: /打开关联工单 #/ })).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: path.join(evidenceDir, "pc-desktop-inspection-exception-work-order.png"),
      fullPage: false,
    });

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/facility-operations");
    await page.getByRole("button", { name: "IoT 告警" }).click();
    await page.getByRole("button", { name: "登记提供方" }).click();
    const providerCode = `E2E_SANDBOX_${suffix}`.toUpperCase();
    await page.getByLabel("编码").fill(providerCode);
    await page.getByLabel("名称").fill("E2E IoT 沙箱");
    await page.getByRole("button", { name: "登记真实状态" }).click();
    await expect(page.getByText("IoT 沙箱提供方已创建")).toBeVisible();
    const provider = dataOf<Array<{ id: number; code: string }>>(
      (await apiJson(request, "get", "/iot-providers", { token })).body
    ).find((item) => item.code === providerCode)!;

    await page.getByRole("button", { name: "绑定设备" }).click();
    const externalKey = `fire-${suffix}`;
    await page.getByLabel("提供方 ID").fill(String(provider.id));
    await page.getByLabel("设备 ID").fill(String(device.id));
    await page.getByLabel("外部设备键").fill(externalKey);
    await page.getByRole("button", { name: "创建绑定" }).click();
    await expect(page.getByText("IoT 设备绑定已生效")).toBeVisible();

    await page.getByRole("button", { name: "注入沙箱事件" }).click();
    await page.getByLabel("提供方 ID").fill(String(provider.id));
    await page.getByLabel("外部设备键").fill(externalKey);
    await page.getByLabel("告警标题").fill("消防泵启动故障 E2E");
    await page.getByLabel("严重度").selectOption("CRITICAL");
    await page.getByLabel("错误码").fill("E2E-101");
    await page.getByRole("button", { name: "发送沙箱事件" }).click();
    await expect(page.getByText("沙箱告警事件已接收")).toBeVisible();
    await page.getByRole("button", { name: /消防泵启动故障 E2E/ }).click();
    await expect(page.getByLabel("IoT 告警详情")).toContainText(/工单/);
    await page.screenshot({
      path: path.join(evidenceDir, "pc-desktop-iot-alarm-correlation.png"),
      fullPage: false,
    });
    await page.getByRole("button", { name: "确认告警" }).click();
    await page.getByPlaceholder("解决原因（必填）").fill("已切换备用泵并复测通过");
    await page.getByRole("button", { name: "解决告警" }).click();
    await page.getByRole("button", { name: "关闭归档" }).click();
    await expect(page.getByLabel("IoT 告警详情")).toContainText("CLOSED");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".drawer-head button").click();
    await page.route("**/api/v1/facility-devices**", (route) => route.abort("failed"));
    await page.getByRole("button", { name: "设备台账" }).click();
    await page.getByRole("button", { name: "刷新真实数据" }).click();
    await expect(page.getByTestId("facility-error")).toContainText("网络或离线");
    const bodySize = await page.locator("body").evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(bodySize.scrollWidth).toBeLessThanOrEqual(bodySize.clientWidth + 1);
    await page.screenshot({
      path: path.join(evidenceDir, "pc-mobile-facility-offline-retry.png"),
      fullPage: true,
    });
  });
});
