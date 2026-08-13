import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATE_FILE = path.join(__dirname, ".stack-state.json");
const REPO_ROOT = path.resolve(__dirname, "../../..");

function killPid(pid: number) {
  try {
    if (process.platform === "win32") {
      execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
    } else {
      try {
        process.kill(-pid, "SIGTERM");
      } catch {
        process.kill(pid, "SIGTERM");
      }
    }
  } catch {
    /* ignore */
  }
}

export default async function globalTeardown() {
  console.log("[e2e-teardown] cleaning stack…");
  if (fs.existsSync(STATE_FILE)) {
    try {
      const st = JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as {
        apiPid?: number;
        webPid?: number;
        apiPort?: number;
        webPort?: number;
      };
      for (const pid of [st.apiPid, st.webPid]) {
        if (pid) killPid(pid);
      }
      // also free ports if orphaned
      if (process.platform === "win32") {
        for (const port of [st.apiPort, st.webPort].filter(Boolean)) {
          try {
            execSync(
              `powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"`,
              { stdio: "ignore", shell: true }
            );
          } catch {
            /* ignore */
          }
        }
      }
    } finally {
      try {
        fs.unlinkSync(STATE_FILE);
      } catch {
        /* ignore */
      }
    }
  }

  // Optional: leave PG container running for speed unless E2E_CLEAN_DOCKER=1
  if (process.env.E2E_CLEAN_DOCKER === "1") {
    try {
      const composeFile = path.join(REPO_ROOT, "infra", "postgres-test", "compose.yaml");
      execSync(`docker compose -f "${composeFile}" down -v`, {
        cwd: REPO_ROOT,
        stdio: "inherit",
        shell: true,
      });
    } catch (e) {
      console.warn("[e2e-teardown] docker down failed", e);
    }
  }
  console.log("[e2e-teardown] done");
}
