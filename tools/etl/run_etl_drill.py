#!/usr/bin/env python3
"""Configurable ETL drill: generate → migrate dry-run → PG apply → checkpoint → interrupt → resume.

Outputs machine-readable JSON + Markdown summary. Never touches production DBs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ETL = Path(__file__).resolve().parent
PY = sys.executable


def run(cmd: list[str], env: dict | None = None) -> dict:
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "cmd": cmd,
        "exit_code": proc.returncode,
        "seconds": round(time.time() - started, 3),
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", choices=["tiny", "fast", "acceptance"], default="fast")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--out-dir",
        default=str(ETL / "out" / "drill"),
    )
    p.add_argument(
        "--database-url",
        default="",
        help="optional; defaults to ETL_DATABASE_URL / TEST_DATABASE_URL env",
    )
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture = out_dir / f"fixture_{args.profile}.json"
    report_json = out_dir / f"drill_{args.profile}.json"
    report_md = out_dir / f"drill_{args.profile}.md"
    checkpoint = out_dir / f"checkpoint_{args.profile}.json"

    import os

    env = os.environ.copy()
    if args.database_url:
        env["ETL_DATABASE_URL"] = args.database_url
        env["TEST_DATABASE_URL"] = args.database_url

    steps: list[dict] = []
    started_at = datetime.now(timezone.utc).isoformat()

    # 1 generate
    steps.append(
        {
            "name": "generate",
            **run(
                [
                    PY,
                    str(ETL / "generate_large_fixture.py"),
                    "--profile",
                    args.profile,
                    "--seed",
                    str(args.seed),
                    "--out",
                    str(fixture),
                ],
                env,
            ),
        }
    )
    if steps[-1]["exit_code"] != 0:
        return _finish(report_json, report_md, started_at, steps, 1)

    # 2 dry-run migrate (default = dry-run when --apply omitted)
    steps.append(
        {
            "name": "migrate_dry_run",
            **run(
                [
                    PY,
                    str(ETL / "migrate.py"),
                    "--fixture",
                    str(fixture),
                    "--checkpoint",
                    str(checkpoint),
                    "--reset-checkpoint",
                    "--report",
                    str(out_dir / f"migrate_dry_{args.profile}.json"),
                ],
                env,
            ),
        }
    )

    # 3 first PG apply (if URL available)
    db_url = env.get("ETL_DATABASE_URL") or env.get("TEST_DATABASE_URL") or env.get("DATABASE_URL")
    if db_url and "prod" not in db_url.lower():
        steps.append(
            {
                "name": "pg_apply_first",
                **run(
                    [
                        PY,
                        str(ETL / "apply_to_postgres.py"),
                        "--fixture",
                        str(fixture),
                    ],
                    env,
                ),
            }
        )
        # 4 second idempotent
        steps.append(
            {
                "name": "pg_apply_idempotent",
                **run(
                    [
                        PY,
                        str(ETL / "apply_to_postgres.py"),
                        "--fixture",
                        str(fixture),
                        "--no-reset-schema",
                    ],
                    env,
                ),
            }
        )
        # 5 simulated interrupt: batch apply with small batch then resume checkpoint
        steps.append(
            {
                "name": "migrate_batch_checkpoint",
                **run(
                    [
                        PY,
                        str(ETL / "migrate.py"),
                        "--fixture",
                        str(fixture),
                        "--apply",
                        "--batch-size",
                        "200",
                        "--checkpoint",
                        str(checkpoint),
                        "--reset-checkpoint",
                        "--report",
                        str(out_dir / f"migrate_partial_{args.profile}.json"),
                        "--failed-out",
                        str(out_dir / f"failed_partial_{args.profile}.json"),
                    ],
                    env,
                ),
            }
        )
        steps.append(
            {
                "name": "migrate_resume_checkpoint",
                **run(
                    [
                        PY,
                        str(ETL / "migrate.py"),
                        "--fixture",
                        str(fixture),
                        "--apply",
                        "--batch-size",
                        "500",
                        "--checkpoint",
                        str(checkpoint),
                        "--report",
                        str(out_dir / f"migrate_resume_{args.profile}.json"),
                        "--failed-out",
                        str(out_dir / f"failed_resume_{args.profile}.json"),
                    ],
                    env,
                ),
            }
        )
    else:
        steps.append(
            {
                "name": "pg_apply_skipped",
                "exit_code": 0,
                "seconds": 0,
                "stdout_tail": "no non-prod ETL_DATABASE_URL; skipped PG apply",
                "stderr_tail": "",
                "cmd": [],
            }
        )

    failed = [s for s in steps if s.get("exit_code", 0) != 0]
    code = 1 if failed else 0
    return _finish(report_json, report_md, started_at, steps, code, fixture)


def _finish(
    report_json: Path,
    report_md: Path,
    started_at: str,
    steps: list[dict],
    code: int,
    fixture: Path | None = None,
) -> int:
    finished = datetime.now(timezone.utc).isoformat()
    payload = {
        "started_at": started_at,
        "finished_at": finished,
        "exit_code": code,
        "fixture": str(fixture) if fixture else None,
        "steps": steps,
        "failed_steps": [s["name"] for s in steps if s.get("exit_code", 0) != 0],
    }
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# ETL Drill Report",
        f"",
        f"- started: `{started_at}`",
        f"- finished: `{finished}`",
        f"- exit_code: **{code}**",
        f"- fixture: `{fixture}`",
        f"",
        f"## Steps",
        f"",
    ]
    for s in steps:
        lines.append(
            f"- **{s['name']}**: exit={s.get('exit_code')} seconds={s.get('seconds')}"
        )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ETL_DRILL_REPORT_JSON={report_json}")
    print(f"ETL_DRILL_REPORT_MD={report_md}")
    print(f"ETL_DRILL={'PASS' if code == 0 else 'FAIL'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
