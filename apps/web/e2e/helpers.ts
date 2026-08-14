import { expect, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ADMIN_USER = process.env.E2E_ADMIN_USER || "admin";
export const ADMIN_PASS = process.env.E2E_ADMIN_PASSWORD || "admin123";
export const LIMITED_USER = process.env.E2E_LIMITED_USER || "e2e_limited";
export const LIMITED_PASS = process.env.E2E_LIMITED_PASSWORD || "limited123";
export const LEASE_VIEWER_USER = process.env.E2E_LEASE_VIEWER_USER || "e2e_lease_viewer";
export const LEASE_VIEWER_PASS = process.env.E2E_LEASE_VIEWER_PASSWORD || "LeaseView!2026";
export const LEASE_SUBMITTER_USER =
  process.env.E2E_LEASE_SUBMITTER_USER || "e2e_lease_submitter";
export const LEASE_SUBMITTER_PASS =
  process.env.E2E_LEASE_SUBMITTER_PASSWORD || "LeaseFlow!2026";

export function apiBase(): string {
  if (process.env.E2E_API_BASE) return process.env.E2E_API_BASE;
  const statePath = path.join(__dirname, ".stack-state.json");
  if (fs.existsSync(statePath)) {
    try {
      const st = JSON.parse(fs.readFileSync(statePath, "utf8")) as {
        apiPort?: number;
      };
      if (st.apiPort) return `http://127.0.0.1:${st.apiPort}/api/v1`;
    } catch {
      /* fall through */
    }
  }
  return "http://127.0.0.1:8010/api/v1";
}

/** Fail hard if API is down — never skip business tests. */
export async function requireApiHealthy(request: APIRequestContext): Promise<void> {
  const base = apiBase().replace(/\/api\/v1\/?$/, "");
  const res = await request.get(`${base}/health`);
  if (!res.ok()) {
    throw new Error(
      `E2E API unhealthy: GET ${base}/health => ${res.status()}. ` +
        "globalSetup must start API; tests must not skip."
    );
  }
}

export async function apiLogin(
  request: APIRequestContext,
  username: string,
  password: string,
  tenantCode = "default"
): Promise<string> {
  await requireApiHealthy(request);
  const res = await request.post(`${apiBase()}/auth/login`, {
    data: { username, password, tenant_code: tenantCode },
  });
  if (!res.ok()) {
    const body = await res.text();
    throw new Error(`API login failed for ${username}: ${res.status()} ${body}`);
  }
  const json = await res.json();
  const token = json?.data?.access_token as string | undefined;
  if (!token) throw new Error(`API login missing token for ${username}`);
  return token;
}

export async function loginAs(
  page: Page,
  username: string,
  password: string
): Promise<void> {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.removeItem("kwzy_access_token");
    localStorage.removeItem("kwzy_refresh_token");
  });
  await page.reload();
  await page.fill("#login-username", username);
  await page.fill("#login-password", password);
  await page.getByTestId("login-submit").click();
  await expect(page).not.toHaveURL(/login/, { timeout: 30000 });
  // ForbiddenView is a child route rendered inside AppLayout.  Asserting the
  // shell avoids Playwright strict-mode failures when both parent and child are
  // present for users whose first post-login route has no matching permission.
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 15000 });
}

export async function expectErrorVisible(page: Page) {
  await expect(page.locator(".error").first()).toBeVisible({ timeout: 10000 });
}

export async function apiJson(
  request: APIRequestContext,
  method: "get" | "post" | "patch" | "put" | "delete",
  pathSuffix: string,
  opts: { token?: string; data?: unknown; headers?: Record<string, string> } = {}
) {
  const headers: Record<string, string> = { ...(opts.headers || {}) };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  const res = await request[method](`${apiBase()}${pathSuffix}`, {
    headers,
    data: opts.data,
  });
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  return { res, body, status: res.status() };
}

export function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}
