/**
 * 自动拉起 PG16 + FastAPI + production frontend。
 * 任一依赖失败即抛错，禁止业务用例 skip。
 */
import { type FullConfig } from "@playwright/test";
import { spawn, type ChildProcessWithoutNullStreams, execSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(WEB_ROOT, "../..");
const API_ROOT = path.join(REPO_ROOT, "apps", "api");
const STATE_FILE = path.join(WEB_ROOT, "e2e", ".stack-state.json");
const LOG_DIR = path.join(WEB_ROOT, "test-results", "stack-logs");
const PG_ENV_FILE = path.join(REPO_ROOT, "infra", "postgres-test", ".env");

const API_PORT = Number(process.env.E2E_API_PORT || 8010);
const WEB_PORT = Number(process.env.E2E_WEB_PORT || 4173);

function localPgConfig() {
  if (!fs.existsSync(PG_ENV_FILE)) {
    throw new Error(`missing gitignored local PostgreSQL env: ${PG_ENV_FILE}`);
  }
  const values: Record<string, string> = {};
  for (const rawLine of fs.readFileSync(PG_ENV_FILE, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const separator = line.indexOf("=");
    values[line.slice(0, separator).trim()] = line.slice(separator + 1).trim();
  }
  const user = values.POSTGRES_USER;
  const password = values.POSTGRES_PASSWORD;
  const database = values.POSTGRES_DB;
  const port = values.POSTGRES_PORT;
  if (!user || !password || !database || !port) {
    throw new Error("local PostgreSQL .env is missing a required POSTGRES_* value");
  }
  return { user, password, database, port };
}

const PG_CONFIG = localPgConfig();
const PG_URL =
  process.env.E2E_DATABASE_URL ||
  `postgresql+psycopg://${encodeURIComponent(PG_CONFIG.user)}:${encodeURIComponent(PG_CONFIG.password)}` +
    `@127.0.0.1:${PG_CONFIG.port}/${encodeURIComponent(PG_CONFIG.database)}`;

function py(): string {
  const win = path.join(API_ROOT, ".venv", "Scripts", "python.exe");
  const nix = path.join(API_ROOT, ".venv", "bin", "python");
  if (fs.existsSync(win)) return win;
  if (fs.existsSync(nix)) return nix;
  throw new Error("apps/api/.venv python not found — create venv before e2e");
}

function waitHttp(url: string, timeoutMs = 180000): Promise<void> {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if ((res.statusCode || 500) < 500) {
          resolve();
          return;
        }
        if (Date.now() - start > timeoutMs) reject(new Error(`timeout ${url} status=${res.statusCode}`));
        else setTimeout(tick, 1000);
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) reject(new Error(`timeout ${url}`));
        else setTimeout(tick, 1000);
      });
    };
    tick();
  });
}

function spawnLogged(
  command: string,
  args: string[],
  cwd: string,
  env: NodeJS.ProcessEnv,
  logName: string
): ChildProcessWithoutNullStreams {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const logPath = path.join(LOG_DIR, logName);
  const logStream = fs.createWriteStream(logPath, { flags: "a" });
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    shell: process.platform === "win32",
    stdio: ["ignore", "pipe", "pipe"],
    detached: process.platform !== "win32",
  });
  child.stdout.on("data", (d) => {
    process.stdout.write(`[stack:${logName}] ${d}`);
    logStream.write(d);
  });
  child.stderr.on("data", (d) => {
    process.stderr.write(`[stack:${logName}] ${d}`);
    logStream.write(d);
  });
  child.on("exit", () => logStream.end());
  return child;
}

function freePort(port: number) {
  try {
    if (process.platform === "win32") {
      execSync(
        `powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"`,
        { stdio: "ignore", shell: true }
      );
    } else {
      execSync(`fuser -k ${port}/tcp || true`, { stdio: "ignore", shell: true });
    }
  } catch {
    /* ignore */
  }
}

export default async function globalSetup(_config: FullConfig) {
  console.log("[e2e-setup] starting full stack…");
  fs.mkdirSync(LOG_DIR, { recursive: true });

  // 1) Docker PG16
  const composeFile = path.join(REPO_ROOT, "infra", "postgres-test", "compose.yaml");
  execSync(`docker compose -f "${composeFile}" up -d`, {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      POSTGRES_USER: PG_CONFIG.user,
      POSTGRES_PASSWORD: PG_CONFIG.password,
      POSTGRES_DB: PG_CONFIG.database,
      POSTGRES_PORT: PG_CONFIG.port,
    },
    stdio: "inherit",
    shell: true,
  });
  const deadline = Date.now() + 120000;
  let healthy = false;
  while (Date.now() < deadline) {
    try {
      const st = execSync(
        'docker inspect --format="{{.State.Health.Status}}" kwzy_party_test_pg',
        { encoding: "utf8", shell: true }
      ).trim();
      if (st === "healthy") {
        healthy = true;
        break;
      }
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  if (!healthy) {
    throw new Error("PostgreSQL 16 container not healthy within 120s");
  }
  console.log("[e2e-setup] PG16 healthy");

  const python = py();
  const alembicWin = path.join(API_ROOT, ".venv", "Scripts", "alembic.exe");
  const alembicNix = path.join(API_ROOT, ".venv", "bin", "alembic");
  const alembicCmd = fs.existsSync(alembicWin) ? alembicWin : alembicNix;

  const commonEnv = {
    ...process.env,
    DATABASE_URL: PG_URL,
    APP_ENV: "test",
    LOCAL_ADMIN_PASSWORD: "admin123",
    JWT_SECRET: "e2e-jwt-secret-not-for-production-32chars",
    ALLOW_ANON_DEV: "false",
  };

  // 2) Alembic base→head
  execSync(`"${alembicCmd}" upgrade head`, {
    cwd: API_ROOT,
    env: commonEnv,
    stdio: "inherit",
    shell: true,
  });
  console.log("[e2e-setup] alembic upgrade head OK");

  // 3) seed
  execSync(`"${python}" "${path.join(REPO_ROOT, "scripts", "e2e_seed.py")}"`, {
    cwd: REPO_ROOT,
    env: commonEnv,
    stdio: "inherit",
    shell: true,
  });
  console.log("[e2e-setup] seed OK");

  freePort(API_PORT);
  freePort(WEB_PORT);

  // 4) API production-like
  const api = spawnLogged(
    python,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", `--port=${API_PORT}`],
    API_ROOT,
    {
      DATABASE_URL: PG_URL,
      APP_ENV: "local",
      DEBUG: "false",
      ALLOW_ANON_DEV: "false",
      JWT_SECRET: "e2e-jwt-secret-not-for-production-32chars",
      LOCAL_ADMIN_PASSWORD: "admin123",
      CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT},http://localhost:${WEB_PORT}`,
      SMS_PROVIDER: "fake",
      WECHAT_PROVIDER: "fake",
      EMAIL_PROVIDER: "fake",
      OSS_PROVIDER: "local",
      OSS_LOCAL_ROOT: path.join(API_ROOT, "data", "e2e-attachments"),
      NOTIFY_PROVIDER: "fake",
      KWZY_E2E_LEAD_CHANNEL_SECRET: "e2e-local-channel-secret-32-bytes",
    },
    "api.log"
  );
  try {
    await waitHttp(`http://127.0.0.1:${API_PORT}/health`, 120000);
  } catch (e) {
    try {
      api.kill();
    } catch {
      /* ignore */
    }
    throw new Error(`API failed to start: ${e}`);
  }
  console.log("[e2e-setup] API healthy on", API_PORT);

  // 5) production frontend build + preview
  execSync("npm run build", {
    cwd: WEB_ROOT,
    env: {
      ...process.env,
      VITE_API_BASE: `http://127.0.0.1:${API_PORT}/api/v1`,
    },
    stdio: "inherit",
    shell: true,
  });
  const web = spawnLogged(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["vite", "preview", "--host", "127.0.0.1", "--port", String(WEB_PORT), "--strictPort"],
    WEB_ROOT,
    { VITE_API_BASE: `http://127.0.0.1:${API_PORT}/api/v1` },
    "web.log"
  );
  try {
    await waitHttp(`http://127.0.0.1:${WEB_PORT}/`, 120000);
  } catch (e) {
    try {
      api.kill();
      web.kill();
    } catch {
      /* ignore */
    }
    throw new Error(`Frontend preview failed to start: ${e}`);
  }
  console.log("[e2e-setup] Frontend preview healthy on", WEB_PORT);

  fs.writeFileSync(
    STATE_FILE,
    JSON.stringify(
      {
        apiPid: api.pid,
        webPid: web.pid,
        apiPort: API_PORT,
        webPort: WEB_PORT,
        apiBase: `http://127.0.0.1:${API_PORT}/api/v1`,
        webBase: `http://127.0.0.1:${WEB_PORT}`,
        logDir: LOG_DIR,
        startedAt: new Date().toISOString(),
      },
      null,
      2
    ),
    "utf8"
  );
  process.env.E2E_BASE_URL = `http://127.0.0.1:${WEB_PORT}`;
  process.env.E2E_API_BASE = `http://127.0.0.1:${API_PORT}/api/v1`;
  console.log("[e2e-setup] stack ready");
}
