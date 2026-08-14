import { test, expect, type APIRequestContext } from "@playwright/test";
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
  "../../../docs/06-implementation/evidence/platform-organization-governance"
);

type DataEnvelope<T> = { data: T };

function dataOf<T>(body: unknown): T {
  return (body as DataEnvelope<T>).data;
}

async function createRoleAndUser(
  request: APIRequestContext,
  token: string,
  prefix: string,
  permissions: string[]
) {
  const suffix = uniqueName(prefix).replace(/-/g, "").slice(-12).toUpperCase();
  const roleCode = `${prefix}_${suffix}`.slice(0, 32).toUpperCase();
  const roleName = `${prefix}角色${suffix}`;
  const roleResponse = await apiJson(request, "post", "/system/roles", {
    token,
    data: {
      code: roleCode,
      name: roleName,
      permission_codes: permissions,
      park_ids: [],
      all_parks: true,
    },
  });
  expect(roleResponse.status).toBe(200);
  const role = dataOf<{ id: number }>(roleResponse.body);
  const username = `${prefix.toLowerCase()}${suffix.toLowerCase()}`.slice(0, 28);
  const realName = `${prefix}用户${suffix}`;
  const password = "Gov-E2E!2026";
  const userResponse = await apiJson(request, "post", "/system/users", {
    token,
    data: {
      username,
      password,
      real_name: realName,
      phone: "13800138000",
      role_ids: [role.id],
      park_ids: [],
      all_parks: true,
    },
  });
  expect(userResponse.status).toBe(200);
  return {
    role: { id: role.id, name: roleName },
    user: { ...dataOf<{ id: number }>(userResponse.body), username, realName, password },
  };
}

test.describe("platform organization governance", () => {
  test.beforeAll(() => fs.mkdirSync(EVIDENCE_DIR, { recursive: true }));
  test.beforeEach(async ({ request }) => requireApiHealthy(request));

  test("admin completes hierarchy, park, position, policy and real HTTP masking journey", async ({
    page,
    request,
  }) => {
    const adminToken = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const readonlyPermissions = [
      "park:read",
      "identity.user.read",
      "identity.role.read",
      "identity.menu.read",
      "identity.org.read",
      "identity.dict.read",
      "identity.param.read",
      "identity.org_governance.read",
    ];
    const subject = await createRoleAndUser(
      request,
      adminToken,
      "MASK",
      readonlyPermissions
    );
    const parkName = uniqueName("组织治理园");
    const parkResponse = await apiJson(request, "post", "/parks", {
      token: adminToken,
      data: { name: parkName },
    });
    expect(parkResponse.status).toBe(200);

    const groupCode = uniqueName("G").replace(/-/g, "").slice(-14).toUpperCase();
    const groupName = `治理集团${groupCode}`;
    const eastCode = `E${groupCode}`.slice(0, 20);
    const westCode = `W${groupCode}`.slice(0, 20);
    const eastName = `东区${groupCode}`;
    const westName = `西区${groupCode}`;
    const positionCode = `P${groupCode}`.slice(0, 20);
    const positionName = `招商主管${groupCode}`;

    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/system");
    await expect(page.getByTestId("organization-governance-panel")).toBeVisible();

    await page.getByTestId("group-code").fill(groupCode);
    await page.getByTestId("group-name").fill(groupName);
    await page.getByTestId("group-form").getByRole("button", { name: "创建集团" }).click();
    await expect(page.getByTestId("governance-success")).toContainText("集团已创建");

    await page.getByTestId("region-group").selectOption({ label: groupName });
    await page.getByTestId("region-code").fill(eastCode);
    await page.getByTestId("region-name").fill(eastName);
    await page.getByTestId("region-form").getByRole("button", { name: "创建区域" }).click();
    await expect(page.getByTestId("governance-success")).toContainText("区域已创建");
    await page.getByTestId("region-group").selectOption({ label: groupName });
    await page.getByTestId("region-code").fill(westCode);
    await page.getByTestId("region-name").fill(westName);
    await page.getByTestId("region-form").getByRole("button", { name: "创建区域" }).click();

    await page.getByTestId("assignment-region").selectOption({ label: eastName });
    await page.getByTestId("assignment-park").selectOption({ label: parkName });
    await page.getByTestId("assignment-reason").fill("E2E 首次归属");
    await page.getByTestId("park-assignment-form").getByRole("button", { name: "确认归属" }).click();
    await expect(page.getByTestId("governance-success")).toContainText("园区归属已更新");
    await page.getByTestId("assignment-region").selectOption({ label: westName });
    await page.getByTestId("assignment-reason").fill("E2E 调区历史");
    await page.getByTestId("park-assignment-form").getByRole("button", { name: "确认归属" }).click();
    await expect(page.getByTestId(`region-row-${westCode}`)).toContainText(parkName);

    await page.getByTestId("position-code").fill(positionCode);
    await page.getByTestId("position-name").fill(positionName);
    await page.getByTestId("position-form").getByRole("button", { name: "创建岗位" }).click();
    await expect(page.getByTestId(`position-row-${positionCode}`)).toBeVisible();
    await page.getByTestId("position-user").selectOption({ label: subject.user.realName });
    await page.getByTestId("position-select").selectOption({ label: positionName });
    await page.getByTestId("position-primary").check();
    await page.getByTestId("user-assignment-form").getByRole("button", { name: "创建任职" }).click();
    await expect(page.getByTestId("assignment-table")).toContainText(subject.user.realName);
    await page.getByTestId("user-assignment-form").getByRole("button", { name: "创建任职" }).click();
    await expect(page.getByTestId("governance-error")).toContainText("数据冲突");

    await page.getByTestId("policy-role").selectOption({ label: subject.role.name });
    await page.getByTestId("policy-mode").selectOption("MASKED");
    await page.getByTestId("field-policy-form").getByRole("button", { name: "保存策略" }).click();
    await expect(page.getByTestId("field-policy-table")).toContainText("MASKED");

    const subjectToken = await apiLogin(
      request,
      subject.user.username,
      subject.user.password
    );
    const projectedUsers = await apiJson(request, "get", "/system/users", {
      token: subjectToken,
    });
    expect(projectedUsers.status).toBe(200);
    const projected = dataOf<Array<{ username: string; phone?: string }>>(
      projectedUsers.body
    ).find((item) => item.username === subject.user.username);
    expect(projected?.phone).toBe("138****8000");

    const hierarchy = await apiJson(
      request,
      "get",
      "/system/organization-governance/hierarchy",
      { token: subjectToken }
    );
    expect(hierarchy.status).toBe(200);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-desktop-organization-governance.png"),
      fullPage: true,
    });
  });

  test("read-only governance is responsive and rejects fabricated write", async ({
    page,
    request,
  }) => {
    const adminToken = await apiLogin(request, ADMIN_USER, ADMIN_PASS);
    const subject = await createRoleAndUser(request, adminToken, "READ", [
      "park:read",
      "identity.user.read",
      "identity.role.read",
      "identity.menu.read",
      "identity.org.read",
      "identity.dict.read",
      "identity.param.read",
      "identity.org_governance.read",
    ]);
    const subjectToken = await apiLogin(
      request,
      subject.user.username,
      subject.user.password
    );
    const denied = await apiJson(
      request,
      "post",
      "/system/organization-governance/groups",
      {
        token: subjectToken,
        headers: { "X-Permissions": "identity.org_governance.write" },
        data: { code: "FORGED_E2E", name: "伪造写入" },
      }
    );
    expect(denied.status).toBe(403);

    await page.setViewportSize({ width: 768, height: 1024 });
    await loginAs(page, subject.user.username, subject.user.password);
    await page.goto("/system");
    await expect(page.getByTestId("governance-readonly")).toBeVisible();
    await expect(page.getByTestId("governance-loading")).toHaveCount(0);
    await expect(page.getByTestId("group-form")).toHaveCount(0);
    await expect(page.getByTestId("field-policy-form")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.body.scrollWidth <= document.documentElement.clientWidth
      )
    ).toBe(true);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-tablet-readonly-governance.png"),
      fullPage: true,
    });
  });

  test("mobile error state retries against the live API", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    let failed = false;
    await page.route("**/system/organization-governance/hierarchy", async (route) => {
      if (!failed) {
        failed = true;
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ code: "DEPENDENCY_UNAVAILABLE", message: "临时失败", data: null }),
        });
        return;
      }
      await route.continue();
    });
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    await page.goto("/system");
    await expect(page.getByTestId("governance-error")).toBeVisible();
    await page.getByTestId("governance-retry").click();
    await expect(page.getByTestId("governance-error")).toHaveCount(0);
    await expect(page.getByTestId("organization-governance-panel")).toBeVisible();
    await expect(page.getByTestId("governance-loading")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.body.scrollWidth <= document.documentElement.clientWidth
      )
    ).toBe(true);
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "pc-mobile-retry-governance.png"),
      fullPage: true,
    });
  });
});
