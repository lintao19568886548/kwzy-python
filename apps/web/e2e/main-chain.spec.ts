/**
 * 浏览器级主链 E2E：依赖真实 API（E2E_API_BASE）与前端 dev/build。
 * 无 API 时跳过业务步骤，仅保证可发现环境。
 */
import { test, expect, type APIRequestContext } from "@playwright/test";

const API = process.env.E2E_API_BASE || "http://127.0.0.1:8000/api/v1";
const ADMIN_USER = process.env.E2E_ADMIN_USER || "admin";
const ADMIN_PASS = process.env.E2E_ADMIN_PASSWORD || "admin123";

async function apiLogin(request: APIRequestContext) {
  const res = await request.post(`${API}/auth/login`, {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  if (!res.ok()) {
    return null;
  }
  const body = await res.json();
  return body?.data?.access_token as string | undefined;
}

test.describe("browser main chain", () => {
  test("login UI and optional API seed flow", async ({ page, request }) => {
    await page.goto("/login");
    await expect(page.locator("#login-username")).toBeVisible();
    await page.fill("#login-username", ADMIN_USER);
    await page.fill("#login-password", ADMIN_PASS);

    const token = await apiLogin(request);
    test.skip(!token, "API not available for full browser main-chain");

    // seed via API then assert UI lists
    const headers = { Authorization: `Bearer ${token}` };
    const parkRes = await request.post(`${API}/parks`, {
      headers,
      data: { name: `E2E-Park-${Date.now()}`, address: "e2e" },
    });
    expect(parkRes.ok()).toBeTruthy();
    const park = (await parkRes.json()).data;

    const partyRes = await request.post(`${API}/parties`, {
      headers,
      data: { name: `E2E-Party-${Date.now()}`, party_type: "ORGANIZATION" },
    });
    expect(partyRes.ok()).toBeTruthy();

    const leadRes = await request.post(`${API}/leads`, {
      headers,
      data: {
        park_id: park.id,
        name: `E2E-Lead-${Date.now()}`,
        contact_phone: "13500135000",
      },
    });
    expect(leadRes.ok()).toBeTruthy();

    // inject token into browser storage and open pages
    await page.evaluate((t) => {
      localStorage.setItem("kwzy_access_token", t);
    }, token!);
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /工作台|运营/ })).toBeVisible({
      timeout: 15000,
    });

    await page.goto("/parties");
    await expect(page.getByRole("heading", { name: /主体/ })).toBeVisible();
    await expect(page.locator("table")).toBeVisible();

    await page.goto("/leads");
    await expect(page.getByRole("heading", { name: /招商|线索/ })).toBeVisible();

    await page.goto("/todos");
    await expect(page.getByRole("heading", { name: /待办/ })).toBeVisible();

    await page.goto("/system");
    await expect(page.getByRole("heading", { name: /系统/ })).toBeVisible();

    // permission denial via API for limited token is covered in pytest; UI logout
    await page.goto("/login");
  });
});
